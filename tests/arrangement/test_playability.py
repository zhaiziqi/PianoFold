"""Behavioral tests for finite, deterministic piano playability costs."""

import math

from pianofold.arrangement.candidates import Voicing
from pianofold.arrangement.playability import voicing_cost
from pianofold.arrangement.profiles import SIMPLE


def test_first_voicing_has_no_transition_cost() -> None:
    """Charging a leap without a previous shape would bias the first slice."""
    current = Voicing((48,), (60,), ("bass", "melody"))

    assert voicing_cost(None, current, SIMPLE) == 0.0


def test_center_moves_past_seven_semitones_cost_more() -> None:
    """Ignoring the seven-semitone free movement makes large relocations cheap."""
    previous = Voicing((48,), (60,), ("bass", "melody"))
    short_move = Voicing((42,), (66,), ("bass", "melody"))
    long_move = Voicing((40,), (68,), ("bass", "melody"))

    assert voicing_cost(previous, long_move, SIMPLE) > voicing_cost(previous, short_move, SIMPLE)


def test_span_over_profile_limit_costs_more_than_nearby_span() -> None:
    """A soft cost must distinguish a playable-width hand from an over-wide hand."""
    near_limit = Voicing((40, 52), (), ("low", "high"))
    over_limit = Voicing((40, 54), (), ("low", "high"))

    assert voicing_cost(None, over_limit, SIMPLE) > voicing_cost(None, near_limit, SIMPLE)


def test_crossing_is_costly_but_finite() -> None:
    """Hand overlap should be discouraged without creating unusable infinite scores."""
    separated = Voicing((48,), (60,), ("bass", "melody"))
    crossed = Voicing((60,), (55,), ("bass", "melody"))

    crossed_cost = voicing_cost(None, crossed, SIMPLE)

    assert crossed_cost > voicing_cost(None, separated, SIMPLE)
    assert math.isfinite(crossed_cost)


def test_high_polyphony_costs_more() -> None:
    """Missing density pressure would make overloaded hands score like sparse ones."""
    sparse = Voicing((40, 43), (), ("a", "b"))
    dense = Voicing((40, 43, 46), (), ("a", "b", "c"))

    assert voicing_cost(None, dense, SIMPLE) > voicing_cost(None, sparse, SIMPLE)
