import subprocess
import sys
from dataclasses import dataclass
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path

import pytest
import torch
from muscriptor import TranscriptionModel
from muscriptor.utils.download import ModelDownloadError

from pianofold.transcription.muscriptor import (
    MuScriptorMPSUnavailableError,
    MuScriptorTranscriber,
    MuScriptorUnavailableError,
    TranscriptionOutput,
    _combine_with_vocal_lead,
)
from pianofold.symbolic.models import Note, ScoreIR, TempoChange
from pianofold.symbolic.serialize import read_score


@dataclass
class NoteStartEvent:
    pitch: int
    time: float
    instrument: str


@dataclass
class NoteEndEvent:
    pitch: int
    time: float
    instrument: str


class FakeModel:
    def __init__(self) -> None:
        self.transcribe_calls = 0
        self.midi_events: list[object] = []

    def transcribe(self, _audio_path: Path, instruments: list[str] | None = None) -> list[object]:
        self.transcribe_calls += 1
        return [NoteStartEvent(64, 0.0, "piano"), NoteEndEvent(64, 0.5, "piano")]

    def detect_beat_grid_for(self, _audio_path: Path, _detect_tempo: str) -> object:
        class FakeGrid:
            bpm = 96.0
            onset_delay = 0.0

            def with_onset_delay(self, _onsets: list[float]):
                return self

        return FakeGrid()

    def events_to_midi_bytes(self, events: object, *, beat_grid: object) -> bytes:
        self.midi_events = list(events)  # type: ignore[arg-type]
        assert getattr(beat_grid, "bpm") == 96.0
        return b"fake-midi"


def test_muscriptor_is_pinned_to_small_mps_float16() -> None:
    """Changing the configured model or accelerator breaks the smoke contract."""
    transcriber = MuScriptorTranscriber()

    assert transcriber.MODEL_SIZE == "small"
    assert transcriber.device == "mps"
    assert transcriber.dtype == "float16"


def test_transcriber_rejects_missing_audio_before_loading_a_model(tmp_path: Path) -> None:
    """A typo in the input path must not trigger an MPS check or weight download."""
    with pytest.raises(FileNotFoundError, match="Audio input does not exist"):
        MuScriptorTranscriber().transcribe(tmp_path / "missing.wav")


def test_transcriber_never_falls_back_to_cpu_when_mps_is_unavailable(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """An unavailable MPS backend must fail before the gated model is imported."""
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"not decoded because MPS is unavailable")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: False)

    with pytest.raises(MuScriptorMPSUnavailableError, match="CPU fallback is disabled"):
        MuScriptorTranscriber().transcribe(audio_path)


def test_transcriber_explains_how_to_access_gated_weights(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """A gated-weight failure must give the operator the required login remedy."""
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"not decoded because loading is replaced")
    monkeypatch.setattr(torch.backends.mps, "is_available", lambda: True)

    def unavailable(**_kwargs: object) -> None:
        raise ModelDownloadError("gated")

    monkeypatch.setattr(TranscriptionModel, "load_model", unavailable)

    with pytest.raises(MuScriptorUnavailableError) as error:
        MuScriptorTranscriber().transcribe(audio_path)

    assert str(error.value) == (
        "MuScriptor weights are not available.\n"
        "Accept the MuScriptor model license on Hugging Face and run:\n"
        "uvx hf auth login"
    )


def test_dual_transcription_keeps_the_full_score_when_vocal_evidence_is_insufficient(tmp_path: Path) -> None:
    """A short constrained voice pass must fall back explicitly, not invent a lead."""
    audio_path = tmp_path / "input.wav"
    audio_path.write_bytes(b"present")
    model = FakeModel()

    output = MuScriptorTranscriber(model=model).transcribe_with_midi(audio_path)

    assert model.transcribe_calls == 2
    assert model.midi_events == [NoteStartEvent(64, 0.0, "piano"), NoteEndEvent(64, 0.5, "piano")]
    assert output.midi_bytes == b"fake-midi"
    assert [(note.pitch, note.start, note.end) for note in output.score.notes] == [(64, 0.0, 0.5)]
    assert output.melody_mode == "instrumental"
    assert output.score.tempo_changes[0].bpm == 96.0


def test_reliable_constrained_voice_replaces_the_unconstrained_voice_track() -> None:
    """A sufficiently long voice pass becomes the protected right-hand lead."""
    voice = tuple(
        Note(f"voice:{index}", 60 + index % 5, index * 0.8, index * 0.8 + 0.45, "voice")
        for index in range(12)
    )
    full_score = ScoreIR(
        (Note("guitar:0", 48, 0.0, 9.8, "acoustic_guitar"), *voice),
        (TempoChange(0.0, 120.0),),
    )
    constrained = ScoreIR(voice, full_score.tempo_changes)

    score, protected_ids, mode = _combine_with_vocal_lead(full_score, constrained)

    assert mode == "vocal"
    assert protected_ids == frozenset(f"lead:{index}" for index in range(12))
    assert {note.id for note in score.notes if note.instrument == "voice"} == protected_ids
    assert any(note.id == "guitar:0" for note in score.notes)


def test_clean_full_mix_voice_is_protected_when_constrained_voice_is_noisy() -> None:
    """The fallback must not let a noisy constrained decoder erase a real singer."""
    voice = tuple(
        Note(f"voice:{index}", 60 + index % 5, index * 0.8, index * 0.8 + 0.45, "voice")
        for index in range(12)
    )
    full_score = ScoreIR(
        (Note("guitar:0", 48, 0.0, 9.8, "acoustic_guitar"), *voice),
        (TempoChange(0.0, 120.0),),
    )
    noisy_constrained = ScoreIR((Note("candidate:0", 72, 0.0, 0.4, "voice"),))

    score, protected_ids, mode = _combine_with_vocal_lead(full_score, noisy_constrained)

    assert mode == "vocal"
    assert protected_ids == frozenset(note.id for note in voice)
    assert {note.id for note in score.notes if note.instrument == "voice"} == protected_ids


def test_smoke_command_rejects_missing_input_without_loading_a_model(tmp_path: Path) -> None:
    """The operational command reports invalid input without touching gated weights."""
    result = subprocess.run(
        [sys.executable, "scripts/smoke_transcribe.py", str(tmp_path / "missing.wav")],
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode != 0
    assert "Audio input does not exist" in result.stderr


def test_smoke_flow_persists_fake_adapter_score_for_the_arranger(tmp_path: Path) -> None:
    """Dropping ScoreIR persistence would block the inspected/arranged next stage."""
    module_spec = spec_from_file_location("smoke_transcribe", "scripts/smoke_transcribe.py")
    assert module_spec and module_spec.loader
    smoke_transcribe = module_from_spec(module_spec)
    module_spec.loader.exec_module(smoke_transcribe)

    class FakeAdapter:
        device = "fake"
        MODEL_SIZE = "fake-small"

        def transcribe_with_midi(self, _audio_path: Path) -> TranscriptionOutput:
            return TranscriptionOutput(b"fake-midi", ScoreIR((Note("source", 64, 0.0, 0.5, "piano"),)))

    output_dir = tmp_path / "smoke"
    result = smoke_transcribe.run(
        tmp_path / "input.wav", FakeAdapter(), output_dir, duration_seconds=1.0
    )

    assert result == (output_dir / "transcription.mid", output_dir / "score_ir.json")
    assert (output_dir / "transcription.mid").read_bytes() == b"fake-midi"
    assert read_score(output_dir / "score_ir.json").notes[0].id == "source"
