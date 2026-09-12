import math

import pytest

from pianofold.symbolic.models import Note, ScoreIR, TempoChange
from pianofold.symbolic.quantize import quantize_score


def test_quantizes_note_boundaries_to_nearest_sixteenth_second_grid() -> None:
    score = ScoreIR((Note("n", 60, 0.13, 0.39, "piano"),))

    result = quantize_score(score, bpm=120, subdivision=4)

    assert result.notes[0].start == pytest.approx(0.125)
    assert result.notes[0].end == pytest.approx(0.375)


def test_quantization_lengthens_subgrid_note_to_one_step() -> None:
    score = ScoreIR((Note("short", 60, 0.12, 0.13, "piano"),))

    result = quantize_score(score, bpm=120, subdivision=4)

    assert result.notes[0].start == pytest.approx(0.125)
    assert result.notes[0].end == pytest.approx(0.25)


@pytest.mark.parametrize("subdivision, expected_step", [(1, 0.5), (2, 0.25), (4, 0.125)])
def test_supports_the_three_grid_subdivisions(subdivision: int, expected_step: float) -> None:
    result = quantize_score(ScoreIR((Note("n", 60, 0.12, 0.24, "piano"),)), 120, subdivision)

    assert result.notes[0].end - result.notes[0].start >= expected_step


@pytest.mark.parametrize("bpm", [0, -1, math.inf, math.nan, True, False])
def test_rejects_invalid_bpm(bpm: float) -> None:
    with pytest.raises(ValueError, match="bpm"):
        quantize_score(ScoreIR(), bpm)


def test_rejects_bpm_with_unrepresentable_float_grid_step() -> None:
    with pytest.raises(ValueError, match="step"):
        quantize_score(ScoreIR(), 5e-324)


@pytest.mark.parametrize("subdivision", [0, 3, 8, 1.5, math.nan])
def test_rejects_invalid_subdivision(subdivision: object) -> None:
    with pytest.raises(ValueError, match="subdivision"):
        quantize_score(ScoreIR(), 120, subdivision)  # type: ignore[arg-type]


def test_preserves_overlaps_attributes_and_tempo_changes() -> None:
    tempo = TempoChange(time=0.2, bpm=90)
    score = ScoreIR(
        notes=(
            Note("a", 60, 0.13, 0.39, "piano", velocity=44),
            Note("b", 64, 0.2, 0.5, "piano", velocity=99),
        ),
        tempo_changes=(tempo,),
    )

    result = quantize_score(score, 120)

    assert result.tempo_changes == (tempo,)
    assert result.notes[0].id == "a"
    assert result.notes[0].velocity == 44
    assert result.notes[0].instrument == "piano"
    assert result.notes[0].end > result.notes[1].start


def test_preserves_an_original_overlap_that_would_snap_to_touching() -> None:
    score = ScoreIR(
        notes=(
            Note("a", 60, 0.0, 0.18, "piano"),
            Note("b", 64, 0.12, 0.30, "piano"),
        )
    )

    result = quantize_score(score, 120, 4)

    assert result.notes[0].end > result.notes[1].start


def test_quantization_is_repeatable() -> None:
    score = ScoreIR((Note("n", 60, 0.13, 0.39, "piano"),))

    assert quantize_score(score, 120, 4) == quantize_score(score, 120, 4)
