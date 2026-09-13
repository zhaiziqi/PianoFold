"""MuScriptor-specific, Apple Silicon-only transcription adapter."""

from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path

from pianofold.symbolic.models import Note, ScoreIR, TempoChange
from pianofold.transcription.base import TranscriptionOutput


_WEIGHTS_HELP = """MuScriptor weights are not available.
Accept the MuScriptor model license on Hugging Face and run:
uvx hf auth login"""


class MuScriptorUnavailableError(RuntimeError):
    """The gated MuScriptor weights cannot be loaded on this machine."""


class MuScriptorMPSUnavailableError(RuntimeError):
    """Apple Metal is required; this smoke command never falls back to CPU."""


class TranscriptionParseError(ValueError):
    """MuScriptor emitted an incomplete or inconsistent note-event stream."""


def events_to_score_ir(events: Iterable[object], *, skip_invalid_ends: bool = False) -> ScoreIR:
    """Convert MuScriptor note events directly into provider-neutral ScoreIR.

    The small duck-typed surface allows synthetic local event fixtures while
    keeping the field adaptation for MuScriptor's public event classes here.
    """
    active: dict[tuple[str, int], deque[tuple[float, int]]] = defaultdict(deque)
    next_index: dict[str, int] = defaultdict(int)
    notes: list[Note] = []

    for event in events:
        if _is_note_end(event):
            instrument, pitch, end = _end_fields(event)
            waiting = active[instrument, pitch]
            if not waiting:
                raise TranscriptionParseError(
                    f"unmatched end for {instrument!r} pitch {pitch}"
                )
            start, index = waiting.popleft()
            if end <= start:
                if skip_invalid_ends:
                    continue
                raise TranscriptionParseError(
                    f"end at {end:.3f}s is not after start at {start:.3f}s for {instrument!r} pitch {pitch}"
                )
            notes.append(Note(f"{instrument}:{index}", pitch, start, end, instrument))
        elif _is_note_start(event):
            instrument, pitch, start = _start_fields(event)
            index = next_index[instrument]
            next_index[instrument] += 1
            active[instrument, pitch].append((start, index))
        # ProgressEvent and unknown advisory events intentionally do not affect notes.

    unfinished = [key for key, starts in active.items() if starts]
    if unfinished:
        descriptions = ", ".join(f"{instrument!r} pitch {pitch}" for instrument, pitch in unfinished)
        raise TranscriptionParseError(f"missing end for {descriptions}")
    return ScoreIR(notes=tuple(notes))


def _is_note_start(event: object) -> bool:
    return "end" not in type(event).__name__.lower() and hasattr(event, "pitch") and hasattr(event, "instrument") and (
        hasattr(event, "start_time") or hasattr(event, "time")
    )


def _is_note_end(event: object) -> bool:
    return hasattr(event, "start_event") or "end" in type(event).__name__.lower() and (
        hasattr(event, "pitch") and hasattr(event, "instrument") and hasattr(event, "time")
    )


def _start_fields(event: object) -> tuple[str, int, float]:
    return (
        str(getattr(event, "instrument")),
        int(getattr(event, "pitch")),
        float(getattr(event, "start_time", getattr(event, "time", None))),
    )


def _end_fields(event: object) -> tuple[str, int, float]:
    if hasattr(event, "start_event"):
        start_event = getattr(event, "start_event")
        return (
            str(getattr(start_event, "instrument")),
            int(getattr(start_event, "pitch")),
            float(getattr(event, "end_time")),
        )
    return (
        str(getattr(event, "instrument")),
        int(getattr(event, "pitch")),
        float(getattr(event, "time")),
    )


class MuScriptorTranscriber:
    """Lazily load the deliberate MuScriptor-small MPS/float16 configuration."""

    MODEL_SIZE = "small"
    device = "mps"
    dtype = "float16"

    def __init__(self, model: object | None = None) -> None:
        self._model = model

    def transcribe(self, audio_path: Path) -> ScoreIR:
        """Transcribe ``audio_path`` directly into provider-neutral ScoreIR."""
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio input does not exist: {audio_path}")
        return events_to_score_ir(self._load_model().transcribe(audio_path))

    def transcribe_to_midi(self, audio_path: Path) -> bytes:
        """Keep the Task 2 raw MIDI workflow available for the smoke script."""
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio input does not exist: {audio_path}")
        return self._load_model().transcribe_to_midi(audio_path)

    def transcribe_with_midi(self, audio_path: Path) -> TranscriptionOutput:
        """Build accompaniment plus a constrained, vocal-first lead line."""
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio input does not exist: {audio_path}")
        model = self._load_model()
        beat_grid = model.detect_beat_grid_for(audio_path, "best-effort")
        events = list(model.transcribe(audio_path))
        full_score, onset_delay = _score_with_timing(events, beat_grid)
        voice_events = list(model.transcribe(audio_path, instruments=["voice"]))
        voice_score, _ = _score_with_timing(voice_events, beat_grid, onset_delay)
        score, melody_note_ids, melody_mode = _combine_with_vocal_lead(full_score, voice_score)
        return TranscriptionOutput(
            midi_bytes=model.events_to_midi_bytes(iter(events), beat_grid=beat_grid),
            score=score,
            melody_note_ids=melody_note_ids,
            melody_mode=melody_mode,
        )

    def _load_model(self):
        if self._model is not None:
            return self._model

        import torch

        if not torch.backends.mps.is_available():
            raise MuScriptorMPSUnavailableError(
                "MuScriptor requires Apple Metal (MPS); CPU fallback is disabled."
            )

        from muscriptor import TranscriptionModel
        from muscriptor.utils.download import ModelDownloadError

        try:
            self._model = TranscriptionModel.load_model(
                weights_path=self.MODEL_SIZE,
                device=self.device,
                dtype=self.dtype,
            )
        except ModelDownloadError as error:
            raise MuScriptorUnavailableError(_WEIGHTS_HELP) from error
        return self._model


def _score_with_timing(
    events: Iterable[object], beat_grid: object | None, onset_delay: float | None = None
) -> tuple[ScoreIR, float]:
    """Keep source times aligned to audio while retaining detected tempo."""
    score = events_to_score_ir(events, skip_invalid_ends=onset_delay is not None)
    if beat_grid is None:
        return score, 0.0
    if onset_delay is None:
        onsets = [note.start for note in score.notes]
        measured = beat_grid.with_onset_delay(onsets)
        onset_delay = float(measured.onset_delay or 0.0)
    bpm = float(beat_grid.bpm)
    notes = tuple(
        Note(
            note.id,
            note.pitch,
            max(0.0, note.start - onset_delay),
            max(max(0.0, note.start - onset_delay) + 0.001, note.end - onset_delay),
            note.instrument,
            note.velocity,
        )
        for note in score.notes
    )
    return ScoreIR(notes, (TempoChange(0.0, bpm),)), onset_delay


def _combine_with_vocal_lead(
    full_score: ScoreIR, voice_score: ScoreIR
) -> tuple[ScoreIR, frozenset[str], str]:
    """Replace unconstrained voice guesses with one reliable lead per onset."""
    constrained = _vocal_leaders(voice_score)
    general_voice = tuple(note for note in full_score.notes if note.instrument == "voice")
    if _reliable_vocal_line(constrained, general_voice):
        accompaniment = [note for note in full_score.notes if note.instrument != "voice"]
        remapped_voice = [
            Note(f"lead:{index}", note.pitch, note.start, note.end, "voice", note.velocity)
            for index, note in enumerate(constrained)
        ]
        score = ScoreIR(tuple(accompaniment + remapped_voice), full_score.tempo_changes)
        return score, frozenset(note.id for note in remapped_voice), "vocal"

    # The unrestricted pass can itself provide a clean, sparse voice track.
    # Prefer that over treating the song as instrumental when the constrained
    # decoder is overly dense or loses EOS markers in a few chunks.
    fallback_voice = _vocal_leaders(ScoreIR(general_voice, full_score.tempo_changes))
    if _reliable_vocal_line(fallback_voice, ()):
        accompaniment = [note for note in full_score.notes if note.instrument != "voice"]
        score = ScoreIR(tuple(accompaniment + list(fallback_voice)), full_score.tempo_changes)
        return score, frozenset(note.id for note in fallback_voice), "vocal"

    return full_score, frozenset(), "instrumental"


def _vocal_leaders(score: ScoreIR) -> tuple[Note, ...]:
    """Keep a monophonic, deterministic lead when the constrained pass overlaps."""
    by_onset: dict[float, list[Note]] = defaultdict(list)
    for note in score.notes:
        by_onset[note.start].append(note)
    return tuple(
        max(notes, key=lambda note: (note.end - note.start, note.pitch, note.id))
        for _, notes in sorted(by_onset.items())
    )


def _reliable_vocal_line(candidate: tuple[Note, ...], general_voice: tuple[Note, ...]) -> bool:
    """Reject short or unsupported constrained output before calling it a vocal."""
    if len(candidate) < 12 or candidate[-1].end - candidate[0].start < 8.0:
        return False
    if not general_voice:
        return True
    matched = sum(
        any(abs(note.start - other.start) <= 0.15 and abs(note.pitch - other.pitch) <= 1 for other in general_voice)
        for note in candidate
    )
    return matched / len(candidate) >= 0.20
