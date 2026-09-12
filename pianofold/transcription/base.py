"""Provider-independent audio-to-symbolic transcription boundary."""

from pathlib import Path
from typing import Protocol

from pianofold.symbolic.models import ScoreIR


class Transcriber(Protocol):
    """A provider that transcribes an audio file to a symbolic score."""

    def transcribe(self, audio_path: Path) -> ScoreIR:
        """Return a provider-independent score for ``audio_path``."""
