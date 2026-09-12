"""Deterministic timing quantization for provider-neutral scores."""

from decimal import Decimal, localcontext
from math import isfinite

from pianofold.symbolic.models import Note, ScoreIR


def quantize_score(score: ScoreIR, bpm: float, subdivision: int = 4) -> ScoreIR:
    """Snap note boundaries to a global beat subdivision.

    ``subdivision`` is the number of grid steps per beat.  Timing arithmetic is
    performed with decimal values derived from the input representations so the
    same score and parameters always produce the same boundaries.
    """
    if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not isfinite(bpm) or bpm <= 0:
        raise ValueError("bpm must be finite and positive")
    if not isinstance(subdivision, int) or isinstance(subdivision, bool) or subdivision not in (1, 2, 4):
        raise ValueError("subdivision must be one of 1, 2, or 4")

    with localcontext() as context:
        context.prec = 50
        step = Decimal("60") / Decimal(str(bpm)) / Decimal(subdivision)
        step_float = float(step)
        if not isfinite(step_float):
            raise ValueError("bpm produces a grid step that cannot be represented as a finite float")

        def snap(value: float) -> float:
            # Add one half before truncating: this is deterministic
            # half-up rounding for non-negative note times.
            ticks = (Decimal(str(value)) / step + Decimal("0.5")).to_integral_value(rounding="ROUND_FLOOR")
            return float(ticks * step)

        quantized = []
        for note in score.notes:
            start = snap(note.start)
            end = snap(note.end)
            if end <= start:
                end = start + step_float
            quantized.append((note, start, end))

        # Snapping can turn a genuine overlap into grid-touching. Preserve
        # each original overlap by extending the note whose end collapsed
        # onto the other note's start by one grid step.
        for index, (left, left_start, left_end) in enumerate(quantized):
            for right_index in range(index + 1, len(quantized)):
                right, right_start, right_end = quantized[right_index]
                if left.start < right.end and right.start < left.end:
                    if left_end <= right_start:
                        quantized[index] = (left, left_start, right_start + step_float)
                        left_end = right_start + step_float
                    if right_end <= left_start:
                        quantized[right_index] = (right, right_start, left_start + step_float)

        notes = []
        for note, start, end in quantized:
            notes.append(
                Note(
                    id=note.id,
                    pitch=note.pitch,
                    start=start,
                    end=end,
                    instrument=note.instrument,
                    velocity=note.velocity,
                )
            )

    return ScoreIR(notes=tuple(notes), tempo_changes=score.tempo_changes)
