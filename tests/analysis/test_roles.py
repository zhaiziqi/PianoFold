"""Behavioral tests for deterministic score-role heuristics."""

from dataclasses import FrozenInstanceError

import pytest

from pianofold.analysis import analyze_roles
from pianofold.analysis.models import RoleAnalysis
from pianofold.symbolic.models import Note, ScoreIR


def synthetic_score() -> ScoreIR:
    """A score with a sustained upper voice, bass, and doubled chord tone."""
    return ScoreIR(
        notes=(
            Note("piano:middle", 64, 0.0, 0.5, "piano"),
            Note("voice:lead", 76, 0.0, 2.0, "vocal"),
            Note("bass:root", 36, 0.0, 1.0, "electric bass"),
            Note("piano:chord", 60, 0.0, 0.5, "piano"),
            Note("piano:next", 74, 1.0, 2.0, "piano"),
            Note("piano:double-a", 60, 1.0, 1.5, "piano"),
            Note("piano:double-b", 72, 1.0, 1.5, "piano"),
            Note("piano:distinct", 67, 1.0, 1.5, "piano"),
            Note("bass:next", 38, 1.0, 2.0, "electric bass"),
        )
    )


def test_role_analysis_scores_are_bounded_and_favor_outer_musical_roles() -> None:
    """Removing role weighting would stop upper voices and bass-labelled lows ranking above chord tones."""
    analysis = analyze_roles(synthetic_score())

    for scores in (analysis.melody, analysis.bass, analysis.harmony):
        assert set(scores) == {note.id for note in synthetic_score().notes}
        assert all(0.0 <= score <= 1.0 for score in scores.values())

    assert analysis.melody["voice:lead"] > analysis.melody["piano:middle"]
    assert analysis.melody["voice:lead"] > analysis.melody["piano:chord"]
    assert analysis.bass["bass:root"] > analysis.bass["piano:middle"]
    assert analysis.bass["bass:next"] > analysis.bass["piano:double-a"]


def test_role_anchors_are_one_per_onset_and_stably_break_score_ties_by_id() -> None:
    """Changing selection order must not make role anchors depend on input ordering."""
    score = ScoreIR(
        notes=(
            Note("z", 60, 0.0, 1.0, "piano"),
            Note("a", 60, 0.0, 1.0, "piano"),
            Note("low-z", 36, 0.0, 1.0, "bass"),
            Note("low-a", 36, 0.0, 1.0, "bass"),
            Note("lead", 76, 1.0, 2.0, "vocal"),
            Note("low-next", 38, 1.0, 2.0, "bass"),
        )
    )

    analysis = analyze_roles(score)

    assert analysis.melody_anchors == frozenset({"a", "lead"})
    assert analysis.bass_anchors == frozenset({"low-a", "low-next"})
    with pytest.raises(FrozenInstanceError):
        analysis.melody_anchors = frozenset()


def test_harmony_rewards_distinct_pitch_classes_and_discounts_doubles() -> None:
    """Ignoring onset pitch-class repetition would give doubled tones harmonic priority."""
    analysis = analyze_roles(synthetic_score())

    assert analysis.harmony["piano:distinct"] > analysis.harmony["piano:double-a"]
    assert analysis.harmony["piano:distinct"] > analysis.harmony["piano:double-b"]
    assert isinstance(analysis, RoleAnalysis)
