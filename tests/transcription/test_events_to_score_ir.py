from dataclasses import dataclass

import pytest

from pianofold.transcription.muscriptor import TranscriptionParseError, events_to_score_ir


@dataclass
class NoteStartEvent:
    pitch: int
    time: float
    instrument: str


@dataclass
class NoteEndEvent:
    pitch: int
    time: float
    instrument: str


@dataclass
class ProgressEvent:
    completed: int
    total: int


def test_events_convert_to_sorted_notes_with_duration() -> None:
    """Dropping event conversion or score ordering loses a provider's note stream."""
    score = events_to_score_ir(
        [
            NoteStartEvent(64, 1.0, "piano"),
            ProgressEvent(0, 1),
            NoteEndEvent(64, 2.0, "piano"),
            NoteStartEvent(60, 0.0, "piano"),
            NoteEndEvent(60, 0.5, "piano"),
        ]
    )

    assert [(note.id, note.pitch, note.start, note.end, note.velocity) for note in score.notes] == [
        ("piano:1", 60, 0.0, 0.5, 80),
        ("piano:0", 64, 1.0, 2.0, 80),
    ]
    assert score.duration == 2.0


def test_overlapping_same_pitch_notes_pair_in_first_in_first_out_order() -> None:
    """Changing active pairing away from FIFO swaps overlapping note ends."""
    score = events_to_score_ir(
        [
            NoteStartEvent(60, 0.0, "piano"),
            NoteStartEvent(60, 0.2, "piano"),
            NoteEndEvent(60, 0.5, "piano"),
            NoteEndEvent(60, 1.0, "piano"),
        ]
    )

    assert [(note.id, note.start, note.end) for note in score.notes] == [
        ("piano:0", 0.0, 0.5),
        ("piano:1", 0.2, 1.0),
    ]


def test_same_pitch_notes_are_isolated_by_instrument() -> None:
    """Ignoring instrument in active keys pairs one instrument's close incorrectly."""
    score = events_to_score_ir(
        [
            NoteStartEvent(60, 0.0, "piano"),
            NoteStartEvent(60, 0.1, "strings"),
            NoteEndEvent(60, 0.4, "strings"),
            NoteEndEvent(60, 0.8, "piano"),
        ]
    )

    assert [(note.id, note.instrument, note.start, note.end) for note in score.notes] == [
        ("piano:0", "piano", 0.0, 0.8),
        ("strings:0", "strings", 0.1, 0.4),
    ]


def test_end_events_can_arrive_in_a_different_pitch_order_than_starts() -> None:
    """Pairing end events by stream position instead of pitch corrupts notes."""
    score = events_to_score_ir(
        [
            NoteStartEvent(60, 0.0, "piano"),
            NoteStartEvent(67, 0.1, "piano"),
            NoteEndEvent(67, 0.4, "piano"),
            NoteEndEvent(60, 0.8, "piano"),
        ]
    )

    assert [(note.pitch, note.start, note.end) for note in score.notes] == [
        (60, 0.0, 0.8),
        (67, 0.1, 0.4),
    ]


def test_unmatched_end_raises_parse_error() -> None:
    """Accepting a close without an active start silently corrupts a transcription."""
    with pytest.raises(TranscriptionParseError, match="unmatched end"):
        events_to_score_ir([NoteEndEvent(60, 1.0, "piano")])


def test_missing_end_raises_parse_error() -> None:
    """Returning with active starts produces incomplete score data."""
    events = [NoteStartEvent(pitch=60, time=0.0, instrument="piano")]
    with pytest.raises(TranscriptionParseError, match="missing end"):
        events_to_score_ir(events)
