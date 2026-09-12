"""Deterministic heuristics for estimating bass notes."""

from pianofold.analysis.models import clamp
from pianofold.symbolic.models import Note, ScoreIR


_BASS_TOKENS = ("bass", "contrabass", "cello", "tuba")


def score_bass_probability(note: Note, context: ScoreIR) -> float:
    """Score a low, bass-like, onset-local bottom note as likely bass."""
    slice_notes = [candidate for candidate in context.notes if candidate.start == note.start]
    lowest = min(candidate.pitch for candidate in slice_notes)
    longest = max((candidate.end - candidate.start for candidate in context.notes), default=0.0)
    duration = (note.end - note.start) / longest if longest else 0.0
    named_bass = float(any(token in note.instrument.casefold() for token in _BASS_TOKENS))
    is_lowest = float(note.pitch == lowest)
    return clamp(0.50 * (1 - note.pitch / 127) + 0.25 * named_bass + 0.15 * is_lowest + 0.10 * duration)
