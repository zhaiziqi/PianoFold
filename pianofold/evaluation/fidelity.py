"""Finite, deterministic symbolic fidelity scores for selected voicings."""

from math import fsum, isfinite
from numbers import Real
from sys import float_info
from typing import Mapping, Sequence

from pianofold.arrangement.candidates import Voicing
from pianofold.symbolic.models import Note

_OUTER_ANCHOR_BONUS = 1.0


def fidelity_score(source_notes: Sequence[Note], voicing: Voicing, salience: Mapping[str, float]) -> float:
    """Score retained salient material, outer anchors, and pitch-class coverage."""
    notes = tuple(source_notes)
    if not notes:
        return 0.0

    retained_ids = set(voicing.source_note_ids)
    note_salience = {note.id: _salience_value(salience.get(note.id, 0.0)) for note in notes}
    retained_mass = fsum(note_salience[note.id] for note in notes if note.id in retained_ids)
    missing_mass = fsum(note_salience[note.id] for note in notes if note.id not in retained_ids)
    outer_ids = {
        min(notes, key=lambda note: (note.pitch, note.id)).id,
        max(notes, key=lambda note: (note.pitch, note.id)).id,
    }
    anchor_bonus = _OUTER_ANCHOR_BONUS if outer_ids <= retained_ids else 0.0
    source_classes = {note.pitch % 12 for note in notes}
    voiced_classes = {pitch % 12 for pitch in voicing.left + voicing.right}
    coverage = len(source_classes & voiced_classes) / len(source_classes)
    return _finite_score(retained_mass + anchor_bonus + coverage - missing_mass)


def _salience_value(value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        return 0.0
    score = float(value)
    return score if isfinite(score) else 0.0


def _finite_score(score: float) -> float:
    return score if isfinite(score) else (float_info.max if score > 0 else -float_info.max)


__all__ = ["fidelity_score"]
