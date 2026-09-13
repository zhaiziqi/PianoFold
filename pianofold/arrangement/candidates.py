"""Finite, deterministic voicing candidates for one simultaneous onset slice."""

from dataclasses import dataclass
from itertools import product
from typing import Mapping, Sequence

from pianofold.arrangement.profiles import DifficultyProfile
from pianofold.symbolic.models import Note


@dataclass(frozen=True)
class Voicing:
    """A two-hand pitch allocation with the retained source note IDs."""

    left: tuple[int, ...]
    right: tuple[int, ...]
    source_note_ids: tuple[str, ...]


def generate_voicing_candidates(
    notes: Sequence[Note], salience: Mapping[str, float], profile: DifficultyProfile
) -> list[Voicing]:
    """Return at most 32 playable hand allocations, in canonical order."""
    if not notes:
        return [Voicing((), (), ())]

    ranked = sorted(notes, key=lambda note: (-salience[note.id], note.pitch, note.id))
    retained = list(ranked[:8])
    retained_ids = {note.id for note in retained}
    for outer in (
        min(notes, key=lambda note: (note.pitch, note.id)),
        max(notes, key=lambda note: (note.pitch, note.id)),
    ):
        if outer.id not in retained_ids:
            retained.append(outer)
            retained_ids.add(outer.id)

    source_note_ids = tuple(sorted(note.id for note in retained))
    candidates: set[Voicing] = set()
    hand_options = (_legal_hands(note.pitch) for note in retained)
    for hands in product(*hand_options):
        left = tuple(sorted(note.pitch for note, hand in zip(retained, hands) if hand == "left"))
        right = tuple(sorted(note.pitch for note, hand in zip(retained, hands) if hand == "right"))
        if _within_limits(left, profile.max_lh_polyphony, profile.max_lh_span) and _within_limits(
            right, profile.max_rh_polyphony, profile.max_rh_span
        ):
            candidates.add(Voicing(left, right, source_note_ids))

    return sorted(candidates, key=lambda candidate: (candidate.left, candidate.right, candidate.source_note_ids))[:32]


def _legal_hands(pitch: int) -> tuple[str, ...]:
    if pitch < 55:
        return ("left",)
    if pitch > 67:
        return ("right",)
    return ("left", "right")


def _within_limits(pitches: tuple[int, ...], max_polyphony: int, max_span: int) -> bool:
    return len(pitches) <= max_polyphony and (not pitches or pitches[-1] - pitches[0] <= max_span)


__all__ = ["Voicing", "generate_voicing_candidates"]
