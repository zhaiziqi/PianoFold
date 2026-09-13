"""Provider-independent audio-to-symbolic transcription boundary."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Protocol

from pianofold.symbolic.models import ScoreIR


@dataclass(frozen=True, slots=True)
class TranscriptionOutput:
    """A complete transcription plus the lead line selected for arranging.

    ``melody_note_ids`` refers to notes in ``score`` that must remain in the
    generated piano line.  Empty IDs signal a clearly labelled instrumental
    fallback rather than an inferred vocal melody.
    """

    midi_bytes: bytes
    score: ScoreIR
    melody_note_ids: frozenset[str] = field(default_factory=frozenset)
    melody_mode: str = "instrumental"


class Transcriber(Protocol):
    """A provider that transcribes an audio file to a symbolic score."""

    def transcribe(self, audio_path: Path) -> ScoreIR:
        """Return a provider-independent score for ``audio_path``."""
