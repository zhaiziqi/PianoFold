import subprocess
import sys
from pathlib import Path

import pytest
import torch
from muscriptor import TranscriptionModel
from muscriptor.utils.download import ModelDownloadError

from pianofold.transcription.muscriptor import (
    MuScriptorMPSUnavailableError,
    MuScriptorTranscriber,
    MuScriptorUnavailableError,
)


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
