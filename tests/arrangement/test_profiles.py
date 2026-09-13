"""Contract tests for arrangement difficulty presets."""

from dataclasses import FrozenInstanceError

import pytest

from pianofold.arrangement.profiles import DifficultyProfile, RICH, SIMPLE, STANDARD, profile_for


def test_presets_have_canonical_lowercase_names_and_limits() -> None:
    assert (SIMPLE.name, STANDARD.name, RICH.name) == ("simple", "standard", "rich")
    assert (SIMPLE.max_rh_polyphony, SIMPLE.max_lh_polyphony) == (2, 2)
    assert (SIMPLE.max_rh_span, SIMPLE.max_lh_span) == (9, 12)
    assert (STANDARD.max_rh_polyphony, STANDARD.max_lh_polyphony) == (3, 3)
    assert (STANDARD.max_rh_span, STANDARD.max_lh_span) == (12, 12)
    assert (RICH.max_rh_polyphony, RICH.max_lh_polyphony) == (4, 4)
    assert (RICH.max_rh_span, RICH.max_lh_span) == (14, 14)


def test_standard_sits_between_simple_and_rich_for_playability_weights() -> None:
    for field in ("leap_weight", "span_weight", "density_weight"):
        simple, standard, rich = (getattr(profile, field) for profile in (SIMPLE, STANDARD, RICH))
        assert simple > standard > rich
    assert SIMPLE.fidelity_weight < STANDARD.fidelity_weight < RICH.fidelity_weight
    assert SIMPLE.max_rh_polyphony < STANDARD.max_rh_polyphony < RICH.max_rh_polyphony


def test_profile_for_is_case_insensitive_and_returns_singletons() -> None:
    assert profile_for("SIMPLE") is SIMPLE
    assert profile_for(" Standard ") is STANDARD
    assert profile_for("rIcH") is RICH
    with pytest.raises(ValueError, match="unknown difficulty profile"):
        profile_for("expert")


def test_profiles_are_frozen() -> None:
    with pytest.raises(FrozenInstanceError):
        SIMPLE.name = "custom"  # type: ignore[misc]


@pytest.mark.parametrize(
    "field",
    [
        "max_rh_polyphony",
        "max_lh_polyphony",
        "max_rh_span",
        "max_lh_span",
        "leap_weight",
        "span_weight",
        "density_weight",
        "fidelity_weight",
    ],
)
def test_profile_rejects_nonpositive_limits_and_weights(field: str) -> None:
    kwargs = dict(
        name="custom",
        max_rh_polyphony=2,
        max_lh_polyphony=2,
        max_rh_span=9,
        max_lh_span=12,
        leap_weight=1.0,
        span_weight=1.0,
        density_weight=1.0,
        fidelity_weight=1.0,
    )
    kwargs[field] = 0
    with pytest.raises(ValueError, match="must be positive"):
        DifficultyProfile(**kwargs)
