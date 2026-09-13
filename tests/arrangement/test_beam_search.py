"""Synthetic integration coverage for difficulty-aware piano arrangement."""

from collections import defaultdict
from statistics import mean
import subprocess
import sys

import pytest

from pianofold.arrangement.profiles import SIMPLE, STANDARD, RICH
from pianofold.symbolic.models import Note, PianoArrangement, ScoreIR, TempoChange


def _arrange(score, profile, beam_width=16):
    from pianofold.arrangement import arrange

    return arrange(score, profile, beam_width)


def four_bar_score() -> ScoreIR:
    """Four 4/4 bars at 120 BPM with changing bass, chords, and melody."""
    notes = []
    for beat in range(16):
        shift = (0, 2, -2, 0)[beat // 4]
        for role, pitch in (
            ("bass", 48 + shift),
            ("chord-a", 55 + shift),
            ("chord-b", 60 + shift),
            ("chord-c", 64 + shift),
            ("chord-d", 67 + shift),
            ("melody", 72 + shift + (0, 2, 4, 2)[beat % 4]),
        ):
            notes.append(Note(f"{role}-{beat}", pitch, beat * 0.5, beat * 0.5 + 0.4, role))
        notes.append(Note(f"drum-{beat}", 36, beat * 0.5, beat * 0.5 + 0.1, "DrUmS"))
    return ScoreIR(tuple(notes), (TempoChange(0.0, 120.0),))


def arrangement_metrics(arrangement: PianoArrangement) -> dict:
    hands = defaultdict(list)
    for note in arrangement.notes:
        hands[note.start, note.hand].append(note.pitch)
    leaps = {}
    spans = {}
    for hand in ("left", "right"):
        centers = [mean(pitches) for (start, side), pitches in sorted(hands.items()) if side == hand]
        leaps[hand] = mean(abs(b - a) for a, b in zip(centers, centers[1:])) if len(centers) > 1 else 0.0
        spans[hand] = max((max(p) - min(p) for (_, side), p in hands.items() if side == hand), default=0)
    ids = {source for note in arrangement.notes for source in note.source_note_ids}
    starts = {start for start, _ in hands}
    return {
        "notes": len(arrangement.notes),
        "density": len(arrangement.notes) / 4,
        "sources": len(ids),
        "melody": sum(source.startswith("melody-") for source in ids),
        "bass": sum(source.startswith("bass-") for source in ids),
        "left_leap": leaps["left"],
        "right_leap": leaps["right"],
        "average_leap": mean(leaps.values()),
        "left_span": spans["left"],
        "right_span": spans["right"],
        "crossings": sum(
            bool(hands[start, "left"] and hands[start, "right"])
            and max(hands[start, "left"]) >= min(hands[start, "right"])
            for start in starts
        ),
    }


@pytest.mark.parametrize("profile", (SIMPLE, STANDARD, RICH))
def test_four_bar_arrangement_is_deterministic_playable_and_traceable(profile):
    """Losing sources, drums leaking through, or ignoring hand limits breaks reduction."""
    score = four_bar_score()
    result = _arrange(score, profile)
    assert result == _arrange(ScoreIR(tuple(reversed(score.notes)), score.tempo_changes), profile)
    assert result.difficulty == profile.name
    assert result.notes
    assert {note.start for note in result.notes} == {beat * 0.5 for beat in range(16)}
    sources = {note.id: note for note in score.notes}
    hands = defaultdict(list)
    for note in result.notes:
        hands[note.start, note.hand].append(note.pitch)
        assert len(note.source_note_ids) == 1
        source = sources[note.source_note_ids[0]]
        assert source.instrument.casefold() not in {"drum", "drums"}
        assert (note.pitch, note.start, note.end) == (source.pitch, source.start, source.end)
    for (_, hand), pitches in hands.items():
        assert len(pitches) <= getattr(profile, f"max_{'lh' if hand == 'left' else 'rh'}_polyphony")
        assert max(pitches) - min(pitches) <= getattr(profile, f"max_{'lh' if hand == 'left' else 'rh'}_span")
    assert tuple(sorted(result.notes, key=lambda n: (n.start, n.pitch, n.hand, n.source_note_ids))) == result.notes


def test_profiles_have_ordered_density_source_retention_and_movement():
    """Ignoring difficulty or discarding rich chord material erases the complexity gradient."""
    simple, standard, rich = [arrangement_metrics(_arrange(four_bar_score(), p)) for p in (SIMPLE, STANDARD, RICH)]
    assert simple["notes"] <= standard["notes"] <= rich["notes"]
    assert simple["sources"] <= standard["sources"] <= rich["sources"]
    assert simple["density"] < rich["density"]
    assert simple["average_leap"] <= rich["average_leap"]


@pytest.mark.parametrize("width", (0, -1, -16))
def test_nonpositive_beam_width_is_rejected_even_for_empty_scores(width):
    """A zero beam must raise an explicit argument error before searching."""
    with pytest.raises(ValueError, match="beam_width"):
        _arrange(ScoreIR(), SIMPLE, width)


@pytest.mark.parametrize("notes", ((), (Note("drum", 36, 0.1, 0.2, "DRUM"),)))
def test_empty_or_drum_only_scores_return_profile_labelled_empty_arrangements(notes):
    """Empty inputs must not crash backtracking or invent playable notes."""
    assert _arrange(ScoreIR(notes), STANDARD) == PianoArrangement((), "standard")


def test_input_timing_is_preserved_without_quantization():
    """Requantizing off-grid source timing would violate the upstream timing boundary."""
    notes = tuple(Note(f"melody-{i}", 72, i * 2 + 0.137, i * 2 + 0.493, "flute") for i in range(4))
    result = _arrange(ScoreIR(notes, (TempoChange(0.0, 93.0),)), SIMPLE)
    assert [(n.start, n.end, n.source_note_ids) for n in result.notes] == [
        (n.start, n.end, (n.id,)) for n in notes
    ]


def test_duplicate_pitches_keep_the_correct_individual_durations_and_source_ids():
    """Pitch-only source lookup would assign the same source twice for orchestral unisons."""
    score = ScoreIR((Note("short", 60, 0.137, 0.413, "piano"), Note("long", 60, 0.137, 1.129, "strings")))
    result = _arrange(score, RICH)
    assert {(n.pitch, n.start, n.end, n.source_note_ids) for n in result.notes} == {
        (60, 0.137, 0.413, ("short",)), (60, 0.137, 1.129, ("long",))
    }


def test_equal_score_hand_allocations_have_a_canonical_tie_break():
    """Arbitrary set iteration must not decide hands when candidate scores tie."""
    result = _arrange(ScoreIR((Note("center", 60, 0.0, 0.4, "piano"),)), SIMPLE)
    assert [(n.pitch, n.hand) for n in result.notes] == [(60, "right")]


def test_explicit_vocal_lead_stays_in_the_right_hand_over_accompaniment():
    from pianofold.arrangement import arrange

    score = ScoreIR((
        Note("bass", 43, 0.0, 1.0, "electric_bass"),
        Note("guitar", 72, 0.0, 1.0, "acoustic_guitar"),
        Note("lead", 64, 0.0, 1.0, "voice"),
    ))
    result = arrange(score, SIMPLE, melody_note_ids=frozenset({"lead"}))
    lead = next(note for note in result.notes if note.source_note_ids == ("lead",))
    assert (lead.pitch, lead.hand) == (64, "right")
    assert lead.velocity > 80


def test_beam_keeps_an_alternative_until_later_movement_resolves_the_choice():
    """Greedy per-slice selection loses the smooth hand allocation available to a wider beam."""
    score = ScoreIR(tuple(Note(f"n-{i}", pitch, i * 2.0, i * 2.0 + 0.4, "piano") for i, pitch in enumerate((60, 68, 68, 68))))
    narrow = _arrange(score, SIMPLE, 1)
    wider = _arrange(score, SIMPLE, 2)
    assert [n.hand for n in narrow.notes] == ["right", "right", "right", "right"]
    assert [n.hand for n in wider.notes] == ["left", "right", "right", "right"]


def test_fidelity_can_be_imported_before_the_public_arranger():
    """Publishing arrange must not break fidelity consumers through a package import cycle."""
    result = subprocess.run(
        [sys.executable, "-c", (
            "from pianofold.evaluation.fidelity import fidelity_score; "
            "from pianofold.arrangement import arrange; "
            "from pianofold.arrangement.candidates import Voicing; "
            "assert fidelity_score((), Voicing((), (), ()), {}) == 0.0"
        )], capture_output=True, text=True, check=False,
    )
    assert result.returncode == 0, result.stderr
