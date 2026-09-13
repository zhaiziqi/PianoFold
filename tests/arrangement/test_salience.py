from pianofold.analysis import analyze_roles
from pianofold.arrangement.salience import SalienceWeights, note_salience, score_salience
from pianofold.symbolic.models import Note, ScoreIR


def _score() -> ScoreIR:
    return ScoreIR(
        notes=(
            Note("melody", 76, 0.0, 2.0, "vocal"),
            Note("harmony-double", 60, 0.0, 0.5, "piano"),
            Note("harmony-neighbor", 64, 0.5, 1.0, "piano"),
        )
    )


def test_default_salience_weights_are_normalized() -> None:
    weights = SalienceWeights()
    assert weights.melody == 0.45
    assert weights.harmony == 0.20
    assert weights.duration == 0.15
    assert weights.rhythm == 0.10
    assert weights.continuity == 0.10
    assert sum((weights.melody, weights.harmony, weights.duration, weights.rhythm, weights.continuity)) == 1.0


def test_note_salience_is_clamped_and_anchor_beats_redundant_harmony() -> None:
    score = _score()
    roles = analyze_roles(score)
    values = score_salience(score, roles)

    assert 0.0 <= note_salience(score.notes[0], score, roles) <= 1.0
    assert all(0.0 <= value <= 1.0 for value in values.values())
    assert values["melody"] > values["harmony-double"]


def test_score_salience_is_repeatable_and_id_keyed() -> None:
    score = _score()
    roles = analyze_roles(score)
    first = score_salience(score, roles)
    assert first == score_salience(score, roles)
    assert list(first) == [note.id for note in score.notes]
