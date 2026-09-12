"""MuScriptor-specific, Apple Silicon-only audio-to-MIDI adapter."""

from pathlib import Path


_WEIGHTS_HELP = """MuScriptor weights are not available.
Accept the MuScriptor model license on Hugging Face and run:
uvx hf auth login"""


class MuScriptorUnavailableError(RuntimeError):
    """The gated MuScriptor weights cannot be loaded on this machine."""


class MuScriptorMPSUnavailableError(RuntimeError):
    """Apple Metal is required; this smoke command never falls back to CPU."""


class MuScriptorTranscriber:
    """Lazily load the deliberate MuScriptor-small MPS/float16 configuration."""

    MODEL_SIZE = "small"
    device = "mps"
    dtype = "float16"

    def __init__(self) -> None:
        self._model = None

    def transcribe(self, audio_path: Path) -> bytes:
        """Transcribe ``audio_path`` without permitting a CPU fallback."""
        if not audio_path.is_file():
            raise FileNotFoundError(f"Audio input does not exist: {audio_path}")
        return self._load_model().transcribe_to_midi(audio_path)

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
