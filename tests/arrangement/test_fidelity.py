"""Behavioral tests for symbolic fidelity scoring."""

from pianofold.arrangement.candidates import Voicing
from pianofold.evaluation.fidelity import fidelity_score
from pianofold.symbolic.models import Note


def _slice() -> tuple[Note, ...]:
    return (
        Note("bass", 40, 0.0, 1.0, "piano"),
        Note("harmony", 55, 0.0, 1.0, "piano"),
        Note("melody", 72, 0.0, 1.0, "piano"),
    )


def test_retaining_outer_high_salience_notes_beats_sparse_low_salience_choice() -> None:
    """A scorer that ignores anchors or salience can prefer an empty accompaniment."""
    notes = _slice()
    salience = {"bass": 0.9, "harmony": 0.1, "melody": 1.0}
    anchored = Voicing((40,), (55, 72), ("bass", "harmony", "melody"))
    sparse = Voicing((), (55,), ("harmony",))

    assert fidelity_score(notes, anchored, salience) > fidelity_score(notes, sparse, salience)


def test_pitch_class_coverage_improves_chord_fidelity() -> None:
    """Dropping chord tones must lower fidelity even when the root is retained."""
    chord = (
        Note("root", 60, 0.0, 1.0, "piano"),
        Note("third", 64, 0.0, 1.0, "piano"),
        Note("fifth", 67, 0.0, 1.0, "piano"),
    )
    salience = {"root": 0.2, "third": 0.2, "fifth": 0.2}
    complete = Voicing((), (60, 64, 67), ("root", "third", "fifth"))
    root_only = Voicing((), (60,), ("root",))

    assert fidelity_score(chord, complete, salience) > fidelity_score(chord, root_only, salience)
