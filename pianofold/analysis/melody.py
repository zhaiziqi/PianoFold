"""Deterministic heuristics for estimating melodic notes."""

from pianofold.analysis.models import clamp
from pianofold.symbolic.models import Note, ScoreIR


_VOCAL_TOKENS = ("vocal", "voice", "sing", "singer", "choir")


def score_melody_probability(note: Note, context: ScoreIR) -> float:
    """Score an upper, sustained, continuous vocal-like note as likely melody."""
    duration = _normalized_duration(note, context)
    neighbors = _same_instrument_neighbors(note, context)
    continuity = _continuity(note, neighbors)
    neighbor_presence = min(len(neighbors), 2) / 2
    vocal = float(any(token in note.instrument.casefold() for token in _VOCAL_TOKENS))
    low_penalty = 0.35 if note.pitch < 48 else 0.0
    return clamp(
        0.30 * (note.pitch / 127)
        + 0.20 * duration
        + 0.15 * continuity
        + 0.20 * vocal
        + 0.10 * neighbor_presence
        - low_penalty
    )


def _normalized_duration(note: Note, context: ScoreIR) -> float:
    longest = max((candidate.end - candidate.start for candidate in context.notes), default=0.0)
    return (note.end - note.start) / longest if longest else 0.0


def _same_instrument_neighbors(note: Note, context: ScoreIR) -> tuple[Note, ...]:
    matching = [
        candidate
        for candidate in context.notes
        if candidate.instrument == note.instrument and candidate.id != note.id
    ]
    previous = [candidate for candidate in matching if (candidate.start, candidate.id) < (note.start, note.id)]
    following = [candidate for candidate in matching if (candidate.start, candidate.id) > (note.start, note.id)]
    result: list[Note] = []
    if previous:
        result.append(max(previous, key=lambda candidate: (candidate.start, candidate.id)))
    if following:
        result.append(min(following, key=lambda candidate: (candidate.start, candidate.id)))
    return tuple(result)


def _continuity(note: Note, neighbors: tuple[Note, ...]) -> float:
    if not neighbors:
        return 0.0
    return sum(1 - abs(note.pitch - neighbor.pitch) / 127 for neighbor in neighbors) / len(neighbors)
