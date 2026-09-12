"""MuScriptor-specific, Apple Silicon-only transcription adapter."""

from collections import defaultdict, deque
from collections.abc import Iterable
from pathlib import Path

from pianofold.symbolic.models import Note, ScoreIR


_WEIGHTS_HELP = """MuScriptor weights are not available.
Accept the MuScriptor model license on Hugging Face and run:
uvx hf auth login"""


class MuScriptorUnavailableError(RuntimeError):
    """The gated MuScriptor weights cannot be loaded on this machine."""


class MuScriptorMPSUnavailableError(RuntimeError):
    """Apple Metal is required; this smoke command never falls back to CPU."""


class TranscriptionParseError(ValueError):
    """MuScriptor emitted an incomplete or inconsistent note-event stream."""


def events_to_score_ir(events: Iterable[object]) -> ScoreIR:
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

    def __init__(self) -> None:
        self._model = None

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
