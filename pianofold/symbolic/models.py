"""Provider-independent symbolic score data."""

from dataclasses import dataclass, field
from math import isfinite


@dataclass(frozen=True, slots=True)
class Note:
    """One performed note in seconds and MIDI pitch space."""

    id: str
    pitch: int
    start: float
    end: float
    instrument: str
    velocity: int = 80

    def __post_init__(self) -> None:
        if not 0 <= self.pitch <= 127:
            raise ValueError("pitch must be in the MIDI range 0..127")
        if not isfinite(self.start) or self.start < 0:
            raise ValueError("start must be a finite value at or above zero")
        if not isfinite(self.end) or self.end <= self.start:
            raise ValueError("end must be finite and after start")
        if not 1 <= self.velocity <= 127:
            raise ValueError("velocity must be in the MIDI range 1..127")


@dataclass(frozen=True, slots=True)
class TempoChange:
    """A tempo anchor, expressed in beats per minute."""

    time: float
    bpm: float

    def __post_init__(self) -> None:
        if not isfinite(self.time) or self.time < 0:
            raise ValueError("tempo change time must be finite and at or above zero")
        if not isfinite(self.bpm) or self.bpm <= 0:
            raise ValueError("tempo change bpm must be finite and positive")


@dataclass(frozen=True, slots=True)
class ScoreIR:
    """A deterministically ordered symbolic transcription."""

    notes: tuple[Note, ...] = field(default_factory=tuple)
    tempo_changes: tuple[TempoChange, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "notes",
            tuple(sorted(self.notes, key=lambda note: (note.start, note.pitch, note.instrument, note.id))),
        )
        object.__setattr__(
            self,
            "tempo_changes",
            tuple(sorted(self.tempo_changes, key=lambda change: change.time)),
        )

    @property
    def duration(self) -> float:
        """End time of the final note, or zero for an empty score."""
        return max((note.end for note in self.notes), default=0.0)
