"""Immutable difficulty presets used by the symbolic arrangement heuristics."""

from dataclasses import dataclass
import math
from numbers import Real


@dataclass(frozen=True)
class DifficultyProfile:
    """Hard hand limits and soft scoring weights for one difficulty level."""

    name: str
    max_rh_polyphony: int
    max_lh_polyphony: int
    max_rh_span: int
    max_lh_span: int
    leap_weight: float
    span_weight: float
    density_weight: float
    fidelity_weight: float

    def __post_init__(self) -> None:
        if not isinstance(self.name, str) or not self.name.strip():
            raise ValueError("profile name must be a non-empty string")
        limits = (
            self.max_rh_polyphony,
            self.max_lh_polyphony,
            self.max_rh_span,
            self.max_lh_span,
        )
        if any(isinstance(value, bool) or not isinstance(value, int) or value <= 0 for value in limits):
            raise ValueError("profile limits must be positive integers")
        weights = (self.leap_weight, self.span_weight, self.density_weight, self.fidelity_weight)
        if any(
            isinstance(value, bool)
            or not isinstance(value, Real)
            or not math.isfinite(float(value))
            or value <= 0
            for value in weights
        ):
            raise ValueError("profile weights must be positive finite numbers")


SIMPLE = DifficultyProfile(
    name="simple",
    max_rh_polyphony=2,
    max_lh_polyphony=2,
    max_rh_span=9,
    max_lh_span=12,
    leap_weight=1.5,
    span_weight=1.5,
    density_weight=2.0,
    fidelity_weight=0.75,
)

STANDARD = DifficultyProfile(
    name="standard",
    max_rh_polyphony=3,
    max_lh_polyphony=3,
    max_rh_span=12,
    max_lh_span=12,
    leap_weight=1.0,
    span_weight=1.0,
    density_weight=1.0,
    fidelity_weight=1.0,
)

RICH = DifficultyProfile(
    name="rich",
    max_rh_polyphony=4,
    max_lh_polyphony=4,
    max_rh_span=14,
    max_lh_span=14,
    leap_weight=0.5,
    span_weight=0.5,
    density_weight=0.5,
    fidelity_weight=1.25,
)

_PROFILES = {profile.name: profile for profile in (SIMPLE, STANDARD, RICH)}


def profile_for(name: str) -> DifficultyProfile:
    """Return the named preset, accepting case and surrounding whitespace."""

    if not isinstance(name, str):
        raise ValueError(f"unknown difficulty profile: {name!r}")
    try:
        return _PROFILES[name.strip().lower()]
    except KeyError as exc:
        raise ValueError(f"unknown difficulty profile: {name!r}") from exc


__all__ = ["DifficultyProfile", "SIMPLE", "STANDARD", "RICH", "profile_for"]
