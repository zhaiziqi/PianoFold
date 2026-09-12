"""Integration tests for deterministic two-hand MIDI export."""

from pathlib import Path
import subprocess
import sys

import mido
import pytest

from pianofold.arrangement.baseline import PianoArrangement, PianoNote
from pianofold.export.midi import arrangement_to_midi
from pianofold.symbolic.models import Note, ScoreIR
from pianofold.symbolic.serialize import score_to_json


def _absolute_messages(track: mido.MidiTrack) -> list[tuple[int, mido.Message]]:
    tick = 0
    output = []
    for message in track:
        tick += message.time
        if message.type in {"note_on", "note_off"}:
            output.append((tick, message))
    return output


def test_export_writes_type_one_named_hand_tracks_with_fixed_piano_notes(tmp_path: Path) -> None:
    """Wrong track layout, program, velocity, pitches, or timing breaks playback."""
    arrangement = PianoArrangement(
        notes=(
            PianoNote(43, 0.0, 0.5, "left", ("lh",)),
            PianoNote(64, 0.0, 1.0, "right", ("rh-long",)),
            PianoNote(60, 1.0, 1.5, "right", ("rh-60",)),
            PianoNote(62, 1.0, 1.25, "right", ("rh-62",)),
        ),
        difficulty="baseline",
    )
    output = tmp_path / "baseline.mid"

    result = arrangement_to_midi(arrangement, output, bpm=120)
    midi = mido.MidiFile(output)

    assert result == output
    assert midi.type == 1
    assert [track.name for track in midi.tracks] == ["Tempo", "Right Hand", "Left Hand"]
    assert midi.tracks[0][1].type == "set_tempo"
    assert midi.tracks[0][1].tempo == 500000
    right = midi.tracks[1]
    left = midi.tracks[2]
    assert next(message for message in right if message.type == "program_change").program == 0
    assert next(message for message in left if message.type == "program_change").program == 0
    assert [(tick, message.type, message.note, message.velocity) for tick, message in _absolute_messages(right)] == [
        (0, "note_on", 64, 80),
        (960, "note_off", 64, 0),
        (960, "note_on", 60, 80),
        (960, "note_on", 62, 80),
        (1200, "note_off", 62, 0),
        (1440, "note_off", 60, 0),
    ]
    assert [(tick, message.type, message.note, message.velocity) for tick, message in _absolute_messages(left)] == [
        (0, "note_on", 43, 80),
        (480, "note_off", 43, 0),
    ]


@pytest.mark.parametrize("bpm", [0, -1, float("inf"), float("nan"), True])
def test_export_rejects_invalid_bpm(tmp_path: Path, bpm: float) -> None:
    """Invalid tempo values must not produce corrupt MIDI timing."""
    with pytest.raises(ValueError, match="bpm"):
        arrangement_to_midi(PianoArrangement((), "baseline"), tmp_path / "out.mid", bpm=bpm)


def test_export_requires_an_existing_parent_directory(tmp_path: Path) -> None:
    """A typo in the destination directory must be reported before writing."""
    output = tmp_path / "missing" / "out.mid"

    with pytest.raises(ValueError, match="parent"):
        arrangement_to_midi(PianoArrangement((), "baseline"), output)


def test_export_lengthens_a_valid_sub_tick_note_to_one_tick(tmp_path: Path) -> None:
    """Independent tick rounding must not place a note-off before its note-on."""
    output = tmp_path / "sub-tick.mid"

    arrangement_to_midi(
        PianoArrangement((PianoNote(60, 0.0004, 0.0005, "right", ("tiny",)),), "baseline"),
        output,
        bpm=120,
    )

    messages = _absolute_messages(mido.MidiFile(output).tracks[1])
    assert [(tick, message.type, message.note) for tick, message in messages] == [
        (0, "note_on", 60),
        (1, "note_off", 60),
    ]


def test_smoke_arrange_loads_quantizes_reduces_and_exports(tmp_path: Path) -> None:
    """Removing any smoke-command stage prevents a persisted score becoming MIDI."""
    score_path = tmp_path / "score_ir.json"
    output_path = tmp_path / "baseline.mid"
    score_path.write_text(
        score_to_json(ScoreIR((Note("source", 64, 0.13, 0.39, "piano"),))),
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, "scripts/smoke_arrange.py", str(score_path), str(output_path), "--bpm", "120"],
        check=True,
        capture_output=True,
        text=True,
    )

    assert output_path.is_file()
    assert "source notes: 1" in completed.stdout
    assert "arrangement notes: 1" in completed.stdout
    assert str(output_path) in completed.stdout
