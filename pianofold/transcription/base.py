"""Raw audio-to-MIDI transcription boundary for the smoke workflow."""

from pathlib import Path
from typing import Protocol


class Transcriber(Protocol):
    """A provider that transcribes an audio file to complete MIDI bytes."""

    def transcribe(self, audio_path: Path) -> bytes:
        """Return a Standard MIDI file for ``audio_path``."""
