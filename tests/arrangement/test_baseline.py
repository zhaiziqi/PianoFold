"""Behavioral tests for the deterministic two-hand baseline reducer."""

from pianofold.arrangement.baseline import baseline_reduce
from pianofold.symbolic.models import Note, ScoreIR


def test_baseline_reduction_omits_drums_and_keeps_outer_notes_per_hand() -> None:
    """A reducer that keeps drums, inner notes, or too many notes is invalid."""
    score = ScoreIR(
        notes=(
            Note("drum-low", 20, 0.0, 0.5, "drum"),
            Note("drums-high", 100, 0.0, 0.5, "DrUmS"),
            Note("rh-60", 60, 0.0, 0.5, "piano"),
            Note("rh-64", 64, 0.0, 0.5, "piano"),
            Note("rh-67", 67, 0.0, 0.5, "piano"),
            Note("rh-72", 72, 0.0, 0.5, "piano"),
            Note("lh-50", 50, 0.0, 0.5, "bass"),
            Note("lh-48", 48, 0.0, 0.5, "bass"),
            Note("lh-43", 43, 0.0, 0.5, "bass"),
            Note("next-rh", 61, 0.5, 1.0, "piano"),
            Note("next-lh", 59, 0.5, 1.0, "bass"),
        )
    )

    arrangement = baseline_reduce(score)

    assert arrangement.difficulty == "baseline"
    assert [
        (note.pitch, note.start, note.end, note.hand, note.source_note_ids)
        for note in arrangement.notes
    ] == [
        (43, 0.0, 0.5, "left", ("lh-43",)),
        (48, 0.0, 0.5, "left", ("lh-48",)),
        (64, 0.0, 0.5, "right", ("rh-64",)),
        (67, 0.0, 0.5, "right", ("rh-67",)),
        (72, 0.0, 0.5, "right", ("rh-72",)),
        (59, 0.5, 1.0, "left", ("next-lh",)),
        (61, 0.5, 1.0, "right", ("next-rh",)),
    ]


def test_baseline_reduction_tie_breaks_by_id_and_is_repeatable() -> None:
    """Changing equal-pitch tie breaking or output ordering changes notation."""
    score = ScoreIR(
        notes=(
            Note("z-rh", 70, 0.0, 0.5, "piano"),
            Note("a-rh", 70, 0.0, 0.5, "piano"),
            Note("z-lh", 50, 0.0, 0.5, "bass"),
            Note("a-lh", 50, 0.0, 0.5, "bass"),
        )
    )

    first = baseline_reduce(score)

    assert first == baseline_reduce(score)
    assert [(note.hand, note.source_note_ids) for note in first.notes] == [
        ("left", ("a-lh",)),
        ("left", ("z-lh",)),
        ("right", ("a-rh",)),
        ("right", ("z-rh",)),
    ]
