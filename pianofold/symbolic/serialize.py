"""Deterministic JSON persistence for :mod:`pianofold.symbolic.models`."""

import json
from pathlib import Path

from pianofold.symbolic.models import Note, ScoreIR, TempoChange


def score_to_json(score: ScoreIR) -> str:
    """Serialize a score into stable, sorted-key JSON."""
    payload = {
        "notes": [
            {
                "end": note.end,
                "id": note.id,
                "instrument": note.instrument,
                "pitch": note.pitch,
                "start": note.start,
                "velocity": note.velocity,
            }
            for note in score.notes
        ],
        "tempo_changes": [
            {"bpm": change.bpm, "time": change.time} for change in score.tempo_changes
        ],
    }
    return json.dumps(payload, sort_keys=True, separators=(",", ":"))


def score_from_json(value: str) -> ScoreIR:
    """Deserialize a score written by :func:`score_to_json`."""
    payload = json.loads(value)
    return ScoreIR(
        notes=tuple(Note(**note) for note in payload["notes"]),
        tempo_changes=tuple(TempoChange(**change) for change in payload["tempo_changes"]),
    )


def write_score(path: Path, score: ScoreIR) -> None:
    """Write a score JSON document to ``path``."""
    path.write_text(score_to_json(score) + "\n", encoding="utf-8")


def read_score(path: Path) -> ScoreIR:
    """Read a score JSON document from ``path``."""
    return score_from_json(path.read_text(encoding="utf-8"))
