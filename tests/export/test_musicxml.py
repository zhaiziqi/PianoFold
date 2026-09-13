"""Integration tests for deterministic two-hand MusicXML export."""

from pathlib import Path

from music21 import clef, converter
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
