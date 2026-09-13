"""Deterministic weighted salience scores for symbolic source notes."""

from dataclasses import dataclass
from math import isfinite

from pianofold.analysis.models import RoleAnalysis, clamp
from pianofold.symbolic.models import Note, ScoreIR


@dataclass(frozen=True, slots=True)
class SalienceWeights:
    """Weights for the five independent salience components."""

    melody: float = 0.45
    harmony: float = 0.20
    duration: float = 0.15
    rhythm: float = 0.10
    continuity: float = 0.10

    def __post_init__(self) -> None:
        values = (self.melody, self.harmony, self.duration, self.rhythm, self.continuity)
        if any(not isfinite(float(value)) or value < 0 for value in values):
            raise ValueError("salience weights must be finite and non-negative")
        if not sum(values):
            raise ValueError("at least one salience weight must be positive")


def note_salience(
    note: Note,
    score: ScoreIR,
    roles: RoleAnalysis,
    weights: SalienceWeights = SalienceWeights(),
) -> float:
    """Return a deterministic, bounded weighted salience score for ``note``."""
    duration = note.end - note.start
    longest = max((candidate.end - candidate.start for candidate in score.notes), default=0.0)
    duration_score = duration / longest if longest else 0.0

    onset_notes = [candidate for candidate in score.notes if candidate.start == note.start]
    cardinality = len(onset_notes)
    if cardinality == 0:
        rhythm_score = 0.0
    elif note.id in roles.melody_anchors or note.id in roles.bass_anchors:
        rhythm_score = 1.0
    else:
        rhythm_score = 1.0 / cardinality

    neighbors = _adjacent_same_instrument(note, score)
    if not neighbors:
        continuity_score = 0.0
    else:
        continuity_score = sum(
            max(0.0, 1.0 - abs(note.pitch - neighbor.pitch) / 5.0)
            for neighbor in neighbors
        ) / len(neighbors)

    value = (
        weights.melody * roles.melody.get(note.id, 0.0)
        + weights.harmony * roles.harmony.get(note.id, 0.0)
        + weights.duration * duration_score
        + weights.rhythm * rhythm_score
        + weights.continuity * continuity_score
    )
    return clamp(value)


def score_salience(score: ScoreIR, roles: RoleAnalysis) -> dict[str, float]:
    """Score every source note, preserving ScoreIR's canonical note order."""
    return {note.id: note_salience(note, score, roles) for note in score.notes}


def _adjacent_same_instrument(note: Note, score: ScoreIR) -> tuple[Note, ...]:
    matching = sorted(
        (candidate for candidate in score.notes if candidate.instrument == note.instrument and candidate.id != note.id),
        key=lambda candidate: (candidate.start, candidate.id),
    )
    before = [candidate for candidate in matching if (candidate.start, candidate.id) < (note.start, note.id)]
    after = [candidate for candidate in matching if (candidate.start, candidate.id) > (note.start, note.id)]
    neighbors: list[Note] = []
    if before:
        neighbors.append(before[-1])
    if after:
        neighbors.append(after[0])
    return tuple(neighbors)
