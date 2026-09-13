"""Immutable results returned by deterministic role analysis."""

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class RoleAnalysis:
    """Per-source-note role scores and onset-local structural anchors."""

    melody: Mapping[str, float]
    bass: Mapping[str, float]
    harmony: Mapping[str, float]
    melody_anchors: frozenset[str]
    bass_anchors: frozenset[str]

    def __post_init__(self) -> None:
        object.__setattr__(self, "melody", _freeze_scores(self.melody))
        object.__setattr__(self, "bass", _freeze_scores(self.bass))
        object.__setattr__(self, "harmony", _freeze_scores(self.harmony))
        object.__setattr__(self, "melody_anchors", frozenset(self.melody_anchors))
        object.__setattr__(self, "bass_anchors", frozenset(self.bass_anchors))


def clamp(value: float) -> float:
    """Return a role score in the public probability interval."""
    return max(0.0, min(1.0, value))


def _freeze_scores(scores: Mapping[str, float]) -> Mapping[str, float]:
    return MappingProxyType({note_id: clamp(float(score)) for note_id, score in scores.items()})
