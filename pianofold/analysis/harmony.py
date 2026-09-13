"""Onset-local harmonic importance heuristic."""

from collections import Counter

from pianofold.analysis.models import clamp
from pianofold.symbolic.models import Note, ScoreIR


def score_harmony_importance(note: Note, context: ScoreIR) -> float:
    """Return pitch-class rarity for ``note`` within its simultaneous onset slice."""
    slice_notes = [candidate for candidate in context.notes if candidate.start == note.start]
    pitch_class_counts = Counter(candidate.pitch % 12 for candidate in slice_notes)
    return clamp(1 / pitch_class_counts[note.pitch % 12])
