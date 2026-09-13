"""Finite, deterministic soft costs for piano voicings."""

from math import fsum, isfinite
from sys import float_info

from pianofold.arrangement.candidates import Voicing
from pianofold.arrangement.profiles import DifficultyProfile

_LEAP_FREE_SEMITONES = 7.0
_VOICE_LEADING_WEIGHT = 0.1


def voicing_cost(previous: Voicing | None, current: Voicing, profile: DifficultyProfile) -> float:
    """Return a finite soft playability cost for ``current`` after ``previous``."""
    components = [
        _span_cost(current.left, profile.max_lh_span, profile.span_weight),
        _span_cost(current.right, profile.max_rh_span, profile.span_weight),
        _density_cost(current.left, profile.density_weight),
        _density_cost(current.right, profile.density_weight),
        _crossing_cost(current, profile.span_weight),
    ]
    if previous is not None:
        for before, after in ((previous.left, current.left), (previous.right, current.right)):
            if before and after:
                movement = abs(_center(after) - _center(before))
                components.append(_weighted(max(0.0, movement - _LEAP_FREE_SEMITONES), profile.leap_weight))
                components.append(_weighted(movement, profile.leap_weight * _VOICE_LEADING_WEIGHT))
    return _finite_sum(components)


def _span_cost(pitches: tuple[int, ...], limit: int, weight: float) -> float:
    if not pitches:
        return 0.0
    return _weighted(max(0, max(pitches) - min(pitches) - limit), weight)


def _density_cost(pitches: tuple[int, ...], weight: float) -> float:
    return _weighted(max(0, len(pitches) - 2), weight)


def _crossing_cost(voicing: Voicing, weight: float) -> float:
    if not voicing.left or not voicing.right:
        return 0.0
    overlap = max(voicing.left) - min(voicing.right)
    return _weighted(overlap + 1, weight) if overlap >= 0 else 0.0


def _center(pitches: tuple[int, ...]) -> float:
    return fsum(pitches) / len(pitches)


def _weighted(value: float, weight: float) -> float:
    try:
        result = value * weight
    except OverflowError:
        return float_info.max
    return result if isfinite(result) else float_info.max


def _finite_sum(components: list[float]) -> float:
    try:
        result = fsum(components)
    except OverflowError:
        return float_info.max
    return result if isfinite(result) else float_info.max


__all__ = ["voicing_cost"]
