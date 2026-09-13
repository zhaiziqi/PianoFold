"""Durable processing behavior with real symbolic and export components."""

from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID, uuid4

import mido
from music21 import converter
import pytest

from pianofold.projects import ProjectMetadata, ProjectResult
from pianofold.projects.metadata import create_project_metadata, read_metadata, write_metadata
from pianofold.projects.pipeline import PianoFoldPipeline
from pianofold.symbolic.models import Note, ScoreIR
from pianofold.symbolic.serialize import read_score


class FakeTranscriber:
    def transcribe(self, audio_path: Path) -> ScoreIR:
        assert audio_path.read_bytes() == b"fake audio"
        return ScoreIR((
            Note("bass", 43, 0.0, 1.04, "bass"),
            Note("melody", 67, 0.0, 1.04, "piano"),
        ))


@pytest.fixture
def project(tmp_path: Path) -> tuple[Path, Path]:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    audio = project_dir / "input.wav"
    audio.write_bytes(b"fake audio")
    return project_dir, audio


def test_pipeline_writes_readable_exports_and_retains_original_score(project) -> None:
    project_dir, audio = project
    result = PianoFoldPipeline(FakeTranscriber()).process(audio, project_dir)

    assert isinstance(result, ProjectResult)
    assert result.project_dir == project_dir
    assert result.metadata.status == "done"
    assert result.metadata.stage == "done"
    assert result.metadata.progress == 1.0
    assert result.metadata.duration == 1.0
    assert result.metadata.error is None
    assert result.metadata == read_metadata(project_dir)
    assert str(UUID(result.metadata.project_id)) == result.metadata.project_id
    assert read_score(project_dir / "score_ir.json").duration == 1.04
    for profile in ("simple", "standard", "rich"):
        midi = mido.MidiFile(project_dir / f"{profile}.mid")
        assert {event.note for track in midi.tracks for event in track if event.type == "note_on"} == {43, 67}
        score = converter.parse(project_dir / f"{profile}.musicxml")
        assert {pitch.midi for pitch in score.pitches} == {43, 67}
    assert not (project_dir / "transcription.mid").exists()


def test_pipeline_persists_every_stage_as_valid_json(project, monkeypatch) -> None:
    import pianofold.projects.pipeline as pipeline_module

    project_dir, audio = project
    snapshots = []
    original_write = pipeline_module.write_metadata

    def capture(directory, metadata):
        path = original_write(directory, metadata)
        snapshots.append(json.loads(path.read_text()))
        return path

    monkeypatch.setattr(pipeline_module, "write_metadata", capture)
    PianoFoldPipeline(FakeTranscriber()).process(audio, project_dir)

    assert [value["stage"] for value in snapshots] == [
        "uploaded", "transcribing", "analyzing", "arranging", "exporting", "done"
    ]
    assert [value["progress"] for value in snapshots] == sorted(value["progress"] for value in snapshots)
    assert len({value["project_id"] for value in snapshots}) == 1
    assert all(value["error"] is None for value in snapshots)


def test_pipeline_preserves_uploaded_project_identity(project) -> None:
    project_dir, audio = project
    uploaded = create_project_metadata(str(uuid4()))
    write_metadata(project_dir, uploaded)

    result = PianoFoldPipeline(FakeTranscriber()).process(audio, project_dir)

    assert result.metadata.project_id == uploaded.project_id


def test_pipeline_uses_canonical_directory_identity(tmp_path: Path) -> None:
    project_dir = tmp_path / str(uuid4())
    project_dir.mkdir()
    audio = project_dir / "input.wav"
    audio.write_bytes(b"fake audio")

    result = PianoFoldPipeline(FakeTranscriber()).process(audio, project_dir)

    assert result.metadata.project_id == project_dir.name


@pytest.mark.parametrize("failure", [RuntimeError("provider failed"), RuntimeError()])
def test_transcription_failure_is_persisted_without_arrangement_outputs(project, failure) -> None:
    class FailingTranscriber:
        def transcribe(self, audio_path):
            raise failure

    project_dir, audio = project
    result = PianoFoldPipeline(FailingTranscriber()).process(audio, project_dir)

    assert result.metadata == read_metadata(project_dir)
    assert result.metadata.status == result.metadata.stage == "failed"
    assert result.metadata.error.strip()
    assert result.metadata.progress < 1.0
    assert {path.name for path in project_dir.iterdir()} == {"input.wav", "metadata.json"}


def test_empty_transcription_fails_without_exports(project) -> None:
    class EmptyTranscriber:
        def transcribe(self, audio_path):
            return ScoreIR()

    project_dir, audio = project
    result = PianoFoldPipeline(EmptyTranscriber()).process(audio, project_dir)

    assert result.metadata.status == "failed"
    assert "no notes" in result.metadata.error.lower()
    assert not list(project_dir.glob("*.mid"))


def test_optional_raw_midi_is_preserved_verbatim(project) -> None:
    class MidiTranscriber(FakeTranscriber):
        def transcribe(self, audio_path):
            raise AssertionError("must use the combined transcription capability")

        def transcribe_with_midi(self, audio_path):
            return SimpleNamespace(
                score=FakeTranscriber().transcribe(audio_path),
                midi_bytes=b"raw provider MIDI\x00\xff",
            )

    project_dir, audio = project
    result = PianoFoldPipeline(MidiTranscriber()).process(audio, project_dir)

    assert result.metadata.status == "done"
    assert (project_dir / "transcription.mid").read_bytes() == b"raw provider MIDI\x00\xff"


@pytest.mark.parametrize("export_behavior", ["raise", "omit"])
def test_export_failure_or_missing_output_never_marks_done(project, monkeypatch, export_behavior) -> None:
    import pianofold.projects.pipeline as pipeline_module

    def broken_export(arrangement, output_path, bpm):
        if export_behavior == "raise":
            raise RuntimeError("export failed")
        return output_path

    monkeypatch.setattr(pipeline_module, "arrangement_to_musicxml", broken_export)
    project_dir, audio = project
    result = PianoFoldPipeline(FakeTranscriber()).process(audio, project_dir)

    assert result.metadata == read_metadata(project_dir)
    assert result.metadata.status == result.metadata.stage == "failed"
    assert result.metadata.error


def test_metadata_round_trip_is_typed_and_immutable(tmp_path: Path) -> None:
    metadata = create_project_metadata(str(uuid4()))
    path = write_metadata(tmp_path, metadata)

    assert path == tmp_path / "metadata.json"
    assert isinstance(read_metadata(tmp_path), ProjectMetadata)
    assert read_metadata(tmp_path) == metadata
    assert read_metadata(tmp_path).profiles == ("simple", "standard", "rich")
    assert metadata.status == metadata.stage == "uploaded"
    assert metadata.progress == 0.0
    assert metadata.error is metadata.duration is None
    with pytest.raises(FrozenInstanceError):
        metadata.status = "done"


@pytest.mark.parametrize("project_id", ["not-a-uuid", "../../outside", uuid4().hex, str(uuid4()).upper()])
def test_metadata_rejects_noncanonical_uuid(project_id) -> None:
    with pytest.raises(ValueError):
        create_project_metadata(project_id)


@pytest.mark.parametrize("updates", [
    {"progress": -0.1}, {"progress": 1.1}, {"progress": float("nan")},
    {"progress": float("inf")}, {"progress": True}, {"progress": "0.1"},
    {"status": "unknown"}, {"stage": "unknown"},
    {"status": "done", "stage": "transcribing"},
    {"status": "processing", "stage": "done"},
    {"status": "uploaded", "stage": "arranging"},
    {"error": "unexpected error"},
    {"status": "failed", "stage": "failed"},
    {"status": "failed", "stage": "failed", "error": " "},
    {"duration": float("nan")}, {"duration": -1},
])
def test_metadata_rejects_invalid_state(updates) -> None:
    with pytest.raises(ValueError):
        replace(create_project_metadata(str(uuid4())), **updates)


def test_atomic_write_leaves_previous_document_if_replacement_fails(tmp_path: Path, monkeypatch) -> None:
    uploaded = create_project_metadata(str(uuid4()))
    write_metadata(tmp_path, uploaded)
    processing = replace(uploaded, status="processing", stage="transcribing", progress=0.1)

    def failed_replace(source, destination):
        assert json.loads(source.read_text())["status"] == "processing"
        assert json.loads(destination.read_text())["status"] == "uploaded"
        raise OSError("replacement interrupted")

    monkeypatch.setattr(Path, "replace", failed_replace)
    with pytest.raises(OSError, match="replacement interrupted"):
        write_metadata(tmp_path, processing)

    assert read_metadata(tmp_path) == uploaded
