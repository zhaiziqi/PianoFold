from dataclasses import FrozenInstanceError

import pytest

from pianofold.symbolic.models import Note, ScoreIR, TempoChange
from pianofold.symbolic.serialize import score_from_json, score_to_json


@pytest.mark.parametrize(
    ("kwargs", "message"),
    [
        ({"pitch": -1}, "pitch"),
        ({"pitch": 128}, "pitch"),
        ({"start": -0.1}, "start"),
        ({"start": 1.0, "end": 1.0}, "end"),
        ({"velocity": 0}, "velocity"),
        ({"velocity": 128}, "velocity"),
    ],
)
def test_note_rejects_invalid_musical_values(kwargs: dict[str, float], message: str) -> None:
    """Removing a Note range check must reject invalid provider output."""
    values = {"id": "piano:0", "pitch": 60, "start": 0.0, "end": 1.0, "instrument": "piano"}
    values.update(kwargs)

    with pytest.raises(ValueError, match=message):
        Note(**values)


def test_score_orders_notes_and_computes_duration() -> None:
    """Changing ScoreIR's sort key or duration calculation breaks consumers."""
    score = ScoreIR(
        notes=(
            Note("b", 61, 1.0, 2.0, "strings"),
            Note("z", 60, 0.0, 1.5, "piano"),
            Note("a", 60, 0.0, 1.0, "piano"),
            Note("c", 60, 0.0, 1.0, "bass"),
        ),
        tempo_changes=(TempoChange(time=0.0, bpm=120.0),),
    )

    assert [note.id for note in score.notes] == ["c", "a", "z", "b"]
    assert score.duration == 2.0


def test_json_round_trip_is_stable() -> None:
    """Changing a serialized field or ordering makes persisted scores unstable."""
    score = ScoreIR(
        notes=(Note("piano:0", 60, 0.0, 0.5, "piano"),),
        tempo_changes=(TempoChange(time=0.0, bpm=90.0),),
    )

    encoded = score_to_json(score)

    assert encoded == score_to_json(score_from_json(encoded))
    assert '"notes"' in encoded
    assert encoded.index('"notes"') < encoded.index('"tempo_changes"')
    assert score_from_json(encoded) == score


def test_note_is_frozen_and_defaults_velocity() -> None:
    """Changing the default velocity or mutability breaks provider-neutral notes."""
    note = Note("piano:0", 60, 0.0, 0.5, "piano")

    assert note.velocity == 80
    with pytest.raises(FrozenInstanceError):
        note.velocity = 1
