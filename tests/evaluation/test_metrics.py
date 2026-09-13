"""Deterministic measurements of onset complexity and traceable fidelity."""

from dataclasses import FrozenInstanceError, fields

import pytest

from pianofold.analysis import analyze_roles
from pianofold.arrangement.salience import score_salience
from pianofold.evaluation.metrics import ArrangementMetrics, calculate_metrics, format_metrics_table
from pianofold.symbolic.models import Note, PianoArrangement, PianoNote, ScoreIR


def test_metrics_calculate_hand_movement_span_crossing_and_retention() -> None:
    source = ScoreIR((
        Note("bass", 43, 0.0, 0.5, "bass"),
        Note("melody", 67, 0.0, 0.5, "piano"),
        Note("harmony", 59, 0.5, 1.0, "piano"),
    ))
    arrangement = PianoArrangement((
        PianoNote(43, 0.0, 0.5, "left", ("bass",)),
        PianoNote(67, 0.0, 0.5, "right", ("melody",)),
        PianoNote(59, 0.5, 1.0, "left", ("harmony",)),
    ), "standard")

    metrics = calculate_metrics(source, arrangement)

    assert metrics.note_count == 3
    assert metrics.notes_per_second == 3.0
    assert metrics.mean_lh_leap == metrics.p95_lh_leap == 16.0
    assert metrics.mean_rh_leap == metrics.p95_rh_leap == 0.0
    assert metrics.max_lh_span == metrics.max_rh_span == 0
    assert metrics.mean_polyphony == 1.5
    assert metrics.hand_crossing_count == metrics.span_violation_count == 0
    assert metrics.salient_retention == 1.0
    assert metrics.melody_anchor_retention == metrics.bass_anchor_retention == 1.0
    assert metrics.pitch_class_coverage == 1.0
    with pytest.raises(FrozenInstanceError):
        metrics.note_count = 10


def test_centers_use_chord_mean_and_skip_absent_hand_onsets() -> None:
    arrangement = PianoArrangement((
        PianoNote(66, 2.0, 3.0, "right", ("d",)),
        PianoNote(40, 1.0, 2.0, "left", ("c",)),
        PianoNote(60, 0.0, 1.0, "right", ("a",)),
        PianoNote(61, 0.0, 1.0, "right", ("b",)),
    ), "simple")
    metrics = calculate_metrics(ScoreIR(), arrangement)
    assert metrics.mean_rh_leap == metrics.p95_rh_leap == 5.5
    assert metrics.mean_lh_leap == 0.0
    assert metrics.max_rh_span == 1
    assert metrics.mean_polyphony == pytest.approx(4 / 3)
    assert metrics == calculate_metrics(ScoreIR(), PianoArrangement(tuple(reversed(arrangement.notes)), "simple"))


def test_p95_uses_nearest_rank_instead_of_max_or_interpolation() -> None:
    # Twenty leaps: eighteen zeros, then 10 and 20. Rank ceil(.95 * 20) is 19.
    pitches = [60] * 19 + [70, 90]
    arrangement = PianoArrangement(tuple(
        PianoNote(pitch, float(i), float(i + 1), hand, (f"{hand}-{i}",))
        for hand in ("left", "right") for i, pitch in enumerate(pitches)
    ), "rich")
    metrics = calculate_metrics(ScoreIR(), arrangement)
    assert metrics.p95_lh_leap == metrics.p95_rh_leap == 10.0
    assert metrics.mean_lh_leap == metrics.mean_rh_leap == 1.5


@pytest.mark.parametrize("difficulty, violations", [("simple", 2), ("standard", 1), ("rich", 0)])
def test_span_violations_use_each_hand_limit_of_arrangement_profile(difficulty: str, violations: int) -> None:
    arrangement = PianoArrangement((
        PianoNote(40, 0.0, 1.0, "left", ("a",)),
        PianoNote(53, 0.0, 1.0, "left", ("b",)),
        PianoNote(60, 0.0, 1.0, "right", ("c",)),
        PianoNote(70, 0.0, 1.0, "right", ("d",)),
    ), difficulty)
    metrics = calculate_metrics(ScoreIR(), arrangement)
    assert metrics.max_lh_span == 13
    assert metrics.max_rh_span == 10
    assert metrics.span_violation_count == violations


def test_crossings_include_equal_pitch_and_count_once_per_onset() -> None:
    arrangement = PianoArrangement((
        PianoNote(65, 0.0, 1.0, "left", ("a",)),
        PianoNote(67, 0.0, 1.0, "left", ("b",)),
        PianoNote(60, 0.0, 1.0, "right", ("c",)),
        PianoNote(61, 0.0, 1.0, "right", ("d",)),
        PianoNote(60, 1.0, 2.0, "left", ("e",)),
        PianoNote(60, 1.0, 2.0, "right", ("f",)),
        PianoNote(40, 2.0, 3.0, "left", ("g",)),
        PianoNote(60, 2.0, 3.0, "right", ("h",)),
    ), "standard")
    assert calculate_metrics(ScoreIR(), arrangement).hand_crossing_count == 2


def test_measurements_use_exact_onsets_not_sustained_note_overlap() -> None:
    arrangement = PianoArrangement((
        PianoNote(80, 2.0, 6.0, "left", ("a",)),
        PianoNote(40, 3.0, 4.0, "left", ("b",)),
        PianoNote(60, 3.0, 4.0, "right", ("c",)),
    ), "simple")
    metrics = calculate_metrics(ScoreIR(), arrangement)
    assert metrics.hand_crossing_count == metrics.max_lh_span == 0
    assert metrics.notes_per_second == 0.5  # Duration includes initial silence.
    assert metrics.mean_polyphony == 1.5


def test_fidelity_uses_unique_known_ids_and_actual_output_pitch_classes() -> None:
    source = ScoreIR((
        Note("bass", 36, 0.0, 1.0, "bass"),
        Note("harmony", 64, 0.0, 0.5, "piano"),
        Note("melody", 79, 0.0, 2.0, "vocal"),
    ))
    arrangement = PianoArrangement((
        PianoNote(48, 0.0, 1.0, "left", ("bass", "bass", "unknown")),
        PianoNote(60, 0.0, 1.0, "right", ("bass",)),
        PianoNote(61, 1.0, 2.0, "right", ("unknown",)),
    ), "standard")
    salience = score_salience(source, analyze_roles(source))
    metrics = calculate_metrics(source, arrangement)
    assert metrics.salient_retention == pytest.approx(salience["bass"] / sum(salience.values()))
    assert metrics.melody_anchor_retention == 0.0
    assert metrics.bass_anchor_retention == 1.0
    assert metrics.pitch_class_coverage == pytest.approx(1 / 3)


def test_empty_scores_and_arrangements_return_zero_without_nan() -> None:
    metrics = calculate_metrics(ScoreIR(), PianoArrangement((), "simple"))
    assert isinstance(metrics, ArrangementMetrics)
    assert all(getattr(metrics, field.name) == 0 for field in fields(metrics))
    source = ScoreIR((Note("a", 60, 0.0, 1.0, "piano"),))
    assert calculate_metrics(source, PianoArrangement((), "simple")) == metrics


def test_unknown_profile_is_explicit_instead_of_silently_using_standard() -> None:
    with pytest.raises(ValueError, match="unknown difficulty profile"):
        calculate_metrics(ScoreIR(), PianoArrangement((), "expert"))


def test_report_contains_all_metrics_and_named_profile_rows() -> None:
    metrics = calculate_metrics(ScoreIR(), PianoArrangement((), "simple"))
    table = format_metrics_table({name: metrics for name in ("simple", "standard", "rich")})
    for name in ("Simple", "Standard", "Rich"):
        assert name in table
    for field in fields(metrics):
        assert field.name in table
    assert "0.000" in table
    assert "nan" not in table
