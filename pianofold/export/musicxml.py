"""MusicXML export for deterministic two-hand piano arrangements."""

from math import isfinite
from pathlib import Path

from music21 import clef, instrument, layout, note, stream, tempo
from music21.musicxml import m21ToXml

from pianofold.symbolic.models import PianoArrangement


def arrangement_to_musicxml(
    arrangement: PianoArrangement, output_path: Path, bpm: float = 120.0
) -> Path:
    """Write a two-staff piano MusicXML score preserving note timing."""
    path = _validate_bpm_and_parent(bpm, output_path)
    score = stream.Score()
    right = stream.PartStaff()
    right.partName = "Right Hand"
    piano = instrument.Piano()
    piano.partId = "Piano"
    piano.instrumentId = "Piano-I1"
    right.insert(0, piano)
    left = stream.PartStaff()
    left.partName = "Left Hand"
    right.insert(0, clef.TrebleClef())
    left.insert(0, clef.BassClef())
    right.insert(0, tempo.MetronomeMark(number=bpm))

    for piano_note in arrangement.notes:
        part = right if piano_note.hand == "right" else left
        exported = note.Note(piano_note.pitch)
        exported.offset = _seconds_to_quarter_length(piano_note.start, bpm)
        exported.duration.quarterLength = _seconds_to_quarter_length(
            piano_note.end - piano_note.start, bpm
        )
        part.insert(exported.offset, exported)

    score.insert(0, right)
    score.insert(0, left)
    score.insert(
        0,
        layout.StaffGroup(
            [right, left], name="Piano", abbreviation="Pno.", symbol="brace", barTogether=True
        ),
    )
    _write_deterministic_musicxml(score, path)
    return path


def _validate_bpm_and_parent(bpm: float, output_path: Path) -> Path:
    if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not isfinite(bpm) or bpm <= 0:
        raise ValueError("bpm must be finite and positive")
    path = Path(output_path)
    if not path.parent.is_dir():
        raise ValueError("output parent directory must exist")
    return path


def _seconds_to_quarter_length(seconds: float, bpm: float) -> float:
    return seconds * bpm / 60


def _write_deterministic_musicxml(score: stream.Score, path: Path) -> None:
    exporter = m21ToXml.ScoreExporter(score)
    document = exporter.parse()
    encoding_date = document.find("./identification/encoding/encoding-date")
    if encoding_date is not None:
        encoding_date.text = "1970-01-01"
    path.write_bytes(exporter.asBytes())
