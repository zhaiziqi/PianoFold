"""Naive deterministic reduction from a score to two piano hands."""

from collections import defaultdict

from pianofold.symbolic.models import PianoArrangement, PianoNote, ScoreIR


def baseline_reduce(score: ScoreIR) -> PianoArrangement:
    """Retain outer simultaneous notes using a fixed middle-C hand split."""
    slices: dict[float, list] = defaultdict(list)
    for note in score.notes:
        if note.instrument.casefold() not in {"drum", "drums"}:
            slices[note.start].append(note)

    selected: list[PianoNote] = []
    for start in sorted(slices):
        notes = slices[start]
        left = sorted((note for note in notes if note.pitch < 60), key=lambda note: (note.pitch, note.id))[:2]
        right = sorted((note for note in notes if note.pitch >= 60), key=lambda note: (-note.pitch, note.id))[:3]
        selected.extend(
            PianoNote(note.pitch, note.start, note.end, "left", (note.id,)) for note in left
        )
        selected.extend(
            PianoNote(note.pitch, note.start, note.end, "right", (note.id,)) for note in right
        )

    return PianoArrangement(
        notes=tuple(sorted(selected, key=lambda note: (note.start, note.pitch, note.hand, note.source_note_ids))),
        difficulty="baseline",
    )
