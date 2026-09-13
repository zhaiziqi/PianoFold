"""Integration tests for deterministic two-hand MusicXML export."""

from datetime import date
from pathlib import Path
from types import SimpleNamespace

from music21 import clef, converter, tempo
from music21.musicxml import m21ToXml
import pytest

from pianofold.export.musicxml import arrangement_to_musicxml
from pianofold.symbolic.models import PianoArrangement, PianoNote


def test_musicxml_export_writes_named_piano_staves_with_note_timing(tmp_path: Path) -> None:
    """Wrong hand, pitch, timing, clef, or part naming breaks readable notation."""
    arrangement = PianoArrangement(
        (
            PianoNote(43, 0.0, 0.5, "left", ("bass",)),
            PianoNote(60, 0.0, 1.0, "right", ("melody",)),
        ),
        "standard",
    )

    output = arrangement_to_musicxml(arrangement, tmp_path / "standard.musicxml", 120.0)
    parsed = converter.parse(output)
    right_notes = list(parsed.parts[0].recurse().notes)
    left_notes = list(parsed.parts[1].recurse().notes)

    assert output == tmp_path / "standard.musicxml"
    assert output.is_file()
    assert [note.pitch.midi for note in right_notes] == [60]
    assert [note.pitch.midi for note in left_notes] == [43]
    assert [note.duration.quarterLength for note in right_notes] == [2.0]
    assert [note.duration.quarterLength for note in left_notes] == [1.0]
    assert isinstance(parsed.parts[0].recurse().getElementsByClass(clef.Clef)[0], clef.TrebleClef)
    assert isinstance(parsed.parts[1].recurse().getElementsByClass(clef.Clef)[0], clef.BassClef)


@pytest.mark.parametrize("bpm", [0, -1, float("inf"), float("nan"), True])
def test_musicxml_export_rejects_invalid_bpm(tmp_path: Path, bpm: float) -> None:
    """Invalid tempo values must not produce corrupt MusicXML timing."""
    with pytest.raises(ValueError, match="bpm"):
        arrangement_to_musicxml(PianoArrangement((), "standard"), tmp_path / "out.musicxml", bpm)


def test_musicxml_export_requires_an_existing_parent_directory(tmp_path: Path) -> None:
    """A typo in the destination directory must be reported before writing."""
    output = tmp_path / "missing" / "out.musicxml"

    with pytest.raises(ValueError, match="parent"):
        arrangement_to_musicxml(PianoArrangement((), "standard"), output)


def test_musicxml_export_is_byte_deterministic_across_repeated_exports(tmp_path: Path) -> None:
    """Unstable score-part IDs would make identical exports differ byte-for-byte."""
    arrangement = PianoArrangement(
        (
            PianoNote(43, 0.0, 0.5, "left", ("bass",)),
            PianoNote(60, 0.0, 1.0, "right", ("melody",)),
        ),
        "standard",
    )
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"

    arrangement_to_musicxml(arrangement, first)
    arrangement_to_musicxml(arrangement, second)

    assert first.read_bytes() == second.read_bytes()


def test_musicxml_export_is_byte_deterministic_across_encoding_dates(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A generated encoding date must not make identical exports differ across days."""
    arrangement = PianoArrangement((PianoNote(60, 0.0, 1.0, "right", ("melody",)),), "standard")
    first = tmp_path / "first.musicxml"
    second = tmp_path / "second.musicxml"

    monkeypatch.setattr(
        m21ToXml, "datetime", SimpleNamespace(date=SimpleNamespace(today=lambda: date(2026, 1, 1)))
    )
    arrangement_to_musicxml(arrangement, first)
    monkeypatch.setattr(
        m21ToXml, "datetime", SimpleNamespace(date=SimpleNamespace(today=lambda: date(2026, 1, 2)))
    )
    arrangement_to_musicxml(arrangement, second)

    assert first.read_bytes() == second.read_bytes()


def test_musicxml_export_emits_the_requested_tempo(tmp_path: Path) -> None:
    """A score-level tempo alone would be omitted from the serialized piano staff."""
    output = tmp_path / "ninety.musicxml"

    arrangement_to_musicxml(
        PianoArrangement((PianoNote(60, 0.0, 1.0, "right", ("melody",)),), "standard"), output, bpm=90
    )

    assert "<per-minute>90</per-minute>" in output.read_text(encoding="utf-8")
    parsed = converter.parse(output)
    assert [mark.number for mark in parsed.recurse().getElementsByClass(tempo.MetronomeMark)] == [90]


def test_musicxml_export_notates_overlapping_hand_rhythms(tmp_path: Path) -> None:
    """Dense overlapping onsets must be split into exportable measures and voices."""
    arrangement = PianoArrangement(
        (
            PianoNote(40, 0.0, 0.125, "left", ("l0",)),
            PianoNote(55, 0.125, 0.25, "right", ("r1",)),
            PianoNote(43, 0.25, 0.375, "left", ("l2",)),
            PianoNote(40, 0.375, 0.5, "left", ("l3",)),
            PianoNote(59, 0.375, 0.5, "right", ("r4",)),
            PianoNote(55, 0.5, 0.625, "right", ("r5",)),
            PianoNote(43, 0.625, 0.75, "left", ("l6",)),
            PianoNote(52, 0.625, 0.75, "left", ("l7",)),
        ),
        "simple",
    )
    output = arrangement_to_musicxml(arrangement, tmp_path / "dense.musicxml", 120.0)

    parsed = converter.parse(output)

    assert sorted(item.pitch.midi for item in parsed.recurse().notes) == [40, 40, 43, 43, 52, 55, 55, 59]
