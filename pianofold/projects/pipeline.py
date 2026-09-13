"""Durable single-project transcription, arrangement, and export workflow."""

from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from pianofold.arrangement import arrange
from pianofold.arrangement.profiles import SIMPLE, STANDARD, RICH
from pianofold.export.midi import arrangement_to_midi
from pianofold.export.musicxml import arrangement_to_musicxml
from pianofold.projects.metadata import create_project_metadata, read_metadata, write_metadata
from pianofold.projects.models import ProjectMetadata, ProjectResult
from pianofold.symbolic.models import ScoreIR
from pianofold.symbolic.quantize import quantize_score
from pianofold.symbolic.serialize import write_score
from pianofold.transcription.base import Transcriber


PROFILES = (SIMPLE, STANDARD, RICH)
DEFAULT_BPM = 120.0


class PianoFoldPipeline:
    """Process an existing upload directory using an injected transcriber."""

    def __init__(self, transcriber: Transcriber) -> None:
        self.transcriber = transcriber

    def process(self, audio_path: Path, project_dir: Path) -> ProjectResult:
        """Persist stage changes and return either done or explicit failed state."""
        metadata = _initial_metadata(project_dir)
        try:
            metadata = replace(metadata, status="processing", stage="transcribing", progress=0.1, error=None, duration=None)
            write_metadata(project_dir, metadata)
            score, midi_bytes, melody_note_ids, melody_mode = self._transcribe(audio_path)
            if not score.notes:
                raise ValueError("Transcription produced no notes")
            if midi_bytes is not None:
                (project_dir / "transcription.mid").write_bytes(midi_bytes)
            write_score(project_dir / "score_ir.json", score)

            notice = None if melody_mode == "vocal" else "No reliable vocal line was detected; this is an instrumental arrangement."
            metadata = replace(metadata, stage="analyzing", progress=0.35, melody_mode=melody_mode, notice=notice)
            write_metadata(project_dir, metadata)
            bpm = score.tempo_changes[0].bpm if score.tempo_changes else DEFAULT_BPM
            quantized = quantize_score(score, bpm)
            metadata = replace(metadata, stage="arranging", progress=0.55)
            write_metadata(project_dir, metadata)
            arrangements = [arrange(quantized, profile, melody_note_ids=melody_note_ids) for profile in PROFILES]

            metadata = replace(metadata, stage="exporting", progress=0.75)
            write_metadata(project_dir, metadata)
            required = [audio_path, project_dir / "score_ir.json"]
            if midi_bytes is not None:
                required.append(project_dir / "transcription.mid")
            for profile, arrangement in zip(PROFILES, arrangements, strict=True):
                midi_path = project_dir / f"{profile.name}.mid"
                xml_path = project_dir / f"{profile.name}.musicxml"
                arrangement_to_midi(arrangement, midi_path, bpm)
                arrangement_to_musicxml(arrangement, xml_path, bpm)
                required.extend((midi_path, xml_path))
            missing = [path.name for path in required if not path.is_file()]
            if missing:
                raise RuntimeError(f"Required output missing: {', '.join(missing)}")
            metadata = replace(metadata, status="done", stage="done", progress=1.0, duration=quantized.duration)
            write_metadata(project_dir, metadata)
        except Exception as error:
            metadata = replace(
                metadata,
                status="failed",
                stage="failed",
                error=str(error).strip() or type(error).__name__,
            )
            write_metadata(project_dir, metadata)
        return ProjectResult(project_dir=project_dir, metadata=metadata)

    def _transcribe(self, audio_path: Path) -> tuple[ScoreIR, bytes | None, frozenset[str], str]:
        combined = getattr(self.transcriber, "transcribe_with_midi", None)
        if callable(combined):
            output = combined(audio_path)
            return (
                output.score,
                output.midi_bytes,
                frozenset(getattr(output, "melody_note_ids", frozenset())),
                getattr(output, "melody_mode", "instrumental"),
            )
        return self.transcriber.transcribe(audio_path), None, frozenset(), "instrumental"


def _initial_metadata(project_dir: Path) -> ProjectMetadata:
    if (project_dir / "metadata.json").is_file():
        return read_metadata(project_dir)
    try:
        metadata = create_project_metadata(project_dir.name)
    except ValueError:
        metadata = create_project_metadata(str(uuid4()))
    write_metadata(project_dir, metadata)
    return metadata
