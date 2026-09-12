"""MIDI export for deterministic two-hand piano arrangements."""

from math import isfinite
from pathlib import Path

import mido

from pianofold.symbolic.models import PianoArrangement

TICKS_PER_BEAT = 480


def arrangement_to_midi(arrangement: PianoArrangement, output_path: Path, bpm: float = 120.0) -> Path:
    """Write a type-1 General MIDI piano file with separate hand tracks."""
    if isinstance(bpm, bool) or not isinstance(bpm, (int, float)) or not isfinite(bpm) or bpm <= 0:
        raise ValueError("bpm must be finite and positive")
    path = Path(output_path)
    if not path.parent.is_dir():
        raise ValueError("output parent directory must exist")

    midi = mido.MidiFile(type=1, ticks_per_beat=TICKS_PER_BEAT)
    tempo = mido.MidiTrack()
    tempo.append(mido.MetaMessage("track_name", name="Tempo", time=0))
    tempo.append(mido.MetaMessage("set_tempo", tempo=mido.bpm2tempo(bpm), time=0))
    midi.tracks.append(tempo)
    midi.tracks.append(_hand_track("Right Hand", (note for note in arrangement.notes if note.hand == "right"), bpm))
    midi.tracks.append(_hand_track("Left Hand", (note for note in arrangement.notes if note.hand == "left"), bpm))
    midi.save(path)
    return path


def _hand_track(name: str, notes: object, bpm: float) -> mido.MidiTrack:
    track = mido.MidiTrack()
    track.append(mido.MetaMessage("track_name", name=name, time=0))
    track.append(mido.Message("program_change", program=0, time=0))
    events = []
    for note in notes:  # type: ignore[union-attr]
        start_tick = _seconds_to_ticks(note.start, bpm)
        end_tick = max(_seconds_to_ticks(note.end, bpm), start_tick + 1)
        events.append((start_tick, 1, note.pitch, 80))
        events.append((end_tick, 0, note.pitch, 0))
    previous_tick = 0
    for tick, event_kind, pitch, velocity in sorted(events, key=lambda event: (event[0], event[1], event[2])):
        message_type = "note_off" if event_kind == 0 else "note_on"
        track.append(mido.Message(message_type, note=pitch, velocity=velocity, time=tick - previous_tick))
        previous_tick = tick
    return track


def _seconds_to_ticks(seconds: float, bpm: float) -> int:
    return round(seconds * bpm / 60 * TICKS_PER_BEAT)
