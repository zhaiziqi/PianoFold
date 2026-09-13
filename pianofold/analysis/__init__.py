"""Deterministic musical-analysis helpers."""

from collections import defaultdict

from pianofold.analysis.bass import score_bass_probability
from pianofold.analysis.harmony import score_harmony_importance
from pianofold.analysis.melody import score_melody_probability
from pianofold.analysis.models import RoleAnalysis
from pianofold.symbolic.models import ScoreIR


def analyze_roles(score: ScoreIR) -> RoleAnalysis:
    """Analyze note roles with deterministic scores and one anchor per onset per role."""
    melody = {note.id: score_melody_probability(note, score) for note in score.notes}
    bass = {note.id: score_bass_probability(note, score) for note in score.notes}
    slices: dict[float, list] = defaultdict(list)
    for note in score.notes:
        slices[note.start].append(note)

    melody_anchors: set[str] = set()
    bass_anchors: set[str] = set()
    for notes in slices.values():
        melody_anchors.add(min(notes, key=lambda note: (-melody[note.id], note.id)).id)
        bass_anchors.add(min(notes, key=lambda note: (-bass[note.id], note.id)).id)

    harmony = {
        note.id: 0.0
        if note.id in melody_anchors or note.id in bass_anchors
        else score_harmony_importance(note, score)
        for note in score.notes
    }
    return RoleAnalysis(melody, bass, harmony, frozenset(melody_anchors), frozenset(bass_anchors))


__all__ = ["RoleAnalysis", "analyze_roles", "score_bass_probability", "score_melody_probability"]
