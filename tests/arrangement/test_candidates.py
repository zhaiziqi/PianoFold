"""Behavioral tests for bounded, deterministic piano voicing candidates."""

from dataclasses import FrozenInstanceError

import pytest

from pianofold.arrangement.candidates import Voicing, generate_voicing_candidates
from pianofold.arrangement.profiles import DifficultyProfile, RICH
from pianofold.symbolic.models import Note


def _onset_slice() -> tuple[tuple[Note, ...], dict[str, float]]:
    notes = (
        Note("bass", 50, 0.0, 1.0, "bass"),
        Note("low-inner", 52, 0.0, 1.0, "piano"),
        Note("center-55", 55, 0.0, 1.0, "piano"),
        Note("center-60-a", 60, 0.0, 1.0, "piano"),
        Note("center-60-b", 60, 0.0, 1.0, "piano"),
        Note("center-64", 64, 0.0, 1.0, "piano"),
        Note("center-67", 67, 0.0, 1.0, "piano"),
        Note("high-inner", 70, 0.0, 1.0, "piano"),
        Note("melody", 71, 0.0, 1.0, "piano"),
        Note("low-discarded", 51, 0.0, 1.0, "piano"),
    )
    salience = {
        "bass": 1.0,
        "melody": 0.99,
        "center-55": 0.90,
        "center-60-a": 0.80,
        "center-60-b": 0.70,
        "center-64": 0.60,
        "center-67": 0.50,
        "low-inner": 0.10,
        "high-inner": 0.20,
        "low-discarded": 0.05,
    }
    return notes, salience


def test_candidates_are_bounded_playable_and_preserve_salient_outer_sources() -> None:
    """Dropping outer anchors or ignoring a hard hand limit loses playable source material."""
    notes, salience = _onset_slice()

    candidates = generate_voicing_candidates(notes, salience, RICH)

    assert 1 <= len(candidates) <= 32
    assert len(candidates) == len(set(candidates))
    for candidate in candidates:
        assert len(candidate.left) <= RICH.max_lh_polyphony
        assert len(candidate.right) <= RICH.max_rh_polyphony
        assert max(candidate.left, default=0) - min(candidate.left, default=0) <= RICH.max_lh_span
        assert max(candidate.right, default=0) - min(candidate.right, default=0) <= RICH.max_rh_span
        assert 50 in candidate.left
        assert 71 in candidate.right
        assert candidate.source_note_ids
        assert all(candidate.source_note_ids)


def test_candidates_offer_alternate_allocations_for_center_pitches() -> None:
    """Treating center pitches as fixed to one hand eliminates required playable alternatives."""
    notes, salience = _onset_slice()

    candidates = generate_voicing_candidates(notes, salience, RICH)

    assert any(60 in candidate.left for candidate in candidates)
    assert any(60 in candidate.right for candidate in candidates)


def test_low_salience_outer_sources_are_forced_back_into_the_retained_slice() -> None:
    """A top-eight-only reducer would silently lose a playable source extreme."""
    notes = tuple(
        Note(note_id, pitch, 0.0, 1.0, "piano")
        for note_id, pitch in (
            ("lowest", 45),
            ("n50", 50),
            ("n55", 55),
            ("n58", 58),
            ("n60", 60),
            ("n62", 62),
            ("n64", 64),
            ("n67", 67),
            ("highest", 75),
        )
    )
    salience = {note.id: float(note.pitch) for note in notes}
    salience["lowest"] = -1.0
    profile = DifficultyProfile("wide", 5, 5, 40, 40, 1.0, 1.0, 1.0, 1.0)

    candidates = generate_voicing_candidates(notes, salience, profile)

    assert candidates
    assert all(45 in candidate.left and 75 in candidate.right for candidate in candidates)
    assert all("lowest" in candidate.source_note_ids for candidate in candidates)


def test_empty_slice_has_one_empty_frozen_voicing() -> None:
    """An empty onset must remain a deterministic state for downstream search."""
    candidates = generate_voicing_candidates((), {}, RICH)

    assert candidates == [Voicing((), (), ())]
    with pytest.raises(FrozenInstanceError):
        candidates[0].left = (60,)  # type: ignore[misc]


def test_candidate_ordering_is_repeatable() -> None:
    """Nondeterministic enumeration would make later arrangement selection unstable."""
    notes, salience = _onset_slice()

    first = generate_voicing_candidates(notes, salience, RICH)

    assert first == generate_voicing_candidates(notes, salience, RICH)
    assert first == sorted(first, key=lambda candidate: (candidate.left, candidate.right, candidate.source_note_ids))
