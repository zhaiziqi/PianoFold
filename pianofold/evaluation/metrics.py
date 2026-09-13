"""Deterministic onset-based arrangement complexity and source fidelity."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass, fields
from math import ceil, fsum

from pianofold.analysis import analyze_roles
from pianofold.arrangement.profiles import profile_for
from pianofold.arrangement.salience import score_salience
from pianofold.symbolic.models import PianoArrangement, PianoNote, ScoreIR


@dataclass(frozen=True, slots=True)
class ArrangementMetrics:
    note_count: int
    notes_per_second: float
    mean_lh_leap: float
    mean_rh_leap: float
    p95_lh_leap: float
    p95_rh_leap: float
    max_lh_span: int
    max_rh_span: int
    mean_polyphony: float
    hand_crossing_count: int
    span_violation_count: int
    salient_retention: float
    melody_anchor_retention: float
    bass_anchor_retention: float
    pitch_class_coverage: float


def calculate_metrics(source: ScoreIR, arrangement: PianoArrangement) -> ArrangementMetrics:
    """Measure exact onset slices, matching the arranger's hand constraints.

    Leaps are adjacent nonempty hand-onset arithmetic-mean pitch differences,
    in semitones, including across rests. P95 selects sorted rank ceil(.95*n)
    (one-based), without interpolation. Spans and polyphony count new onsets,
    not held notes. A crossing is one onset with max(LH) >= min(RH), including
    unisons, as in the arranger. Each over-limit hand-onset is one violation.

    Density divides output note count by the latest output end time (including
    initial silence). Salient retention is retained source-ID salience mass /
    total salience mass; anchor retention uses the current role-analysis sets.
    Repeated and unknown IDs cannot increase retention. Pitch-class coverage
    compares global unique output classes with global unique source classes.
    All empty denominators yield zero; unknown difficulty names raise ValueError.
    """
    profile = profile_for(arrangement.difficulty)
    onsets: dict[float, list[PianoNote]] = defaultdict(list)
    for note in arrangement.notes:
        onsets[note.start].append(note)

    centers: dict[str, list[float]] = {"left": [], "right": []}
    spans = {"left": 0, "right": 0}
    crossings = violations = 0
    for _, notes in sorted(onsets.items()):
        pitches = {
            hand: [note.pitch for note in notes if note.hand == hand]
            for hand in centers
        }
        for hand, limit in (("left", profile.max_lh_span), ("right", profile.max_rh_span)):
            if pitches[hand]:
                span = max(pitches[hand]) - min(pitches[hand])
                spans[hand] = max(spans[hand], span)
                violations += int(span > limit)
                centers[hand].append(fsum(pitches[hand]) / len(pitches[hand]))
        if pitches["left"] and pitches["right"]:
            crossings += int(max(pitches["left"]) >= min(pitches["right"]))

    leaps = {
        hand: [abs(after - before) for before, after in zip(values, values[1:])]
        for hand, values in centers.items()
    }
    retained_ids = {source_id for note in arrangement.notes for source_id in note.source_note_ids}
    roles = analyze_roles(source)
    salience = score_salience(source, roles)
    source_classes = {note.pitch % 12 for note in source.notes}
    output_classes = {note.pitch % 12 for note in arrangement.notes}
    duration = max((note.end for note in arrangement.notes), default=0.0)

    return ArrangementMetrics(
        note_count=len(arrangement.notes),
        notes_per_second=_ratio(len(arrangement.notes), duration),
        mean_lh_leap=_mean(leaps["left"]),
        mean_rh_leap=_mean(leaps["right"]),
        p95_lh_leap=_p95(leaps["left"]),
        p95_rh_leap=_p95(leaps["right"]),
        max_lh_span=spans["left"],
        max_rh_span=spans["right"],
        mean_polyphony=_ratio(len(arrangement.notes), len(onsets)),
        hand_crossing_count=crossings,
        span_violation_count=violations,
        salient_retention=_ratio(
            fsum(value for note_id, value in salience.items() if note_id in retained_ids),
            fsum(salience.values()),
        ),
        melody_anchor_retention=_ratio(len(roles.melody_anchors & retained_ids), len(roles.melody_anchors)),
        bass_anchor_retention=_ratio(len(roles.bass_anchors & retained_ids), len(roles.bass_anchors)),
        pitch_class_coverage=_ratio(len(source_classes & output_classes), len(source_classes)),
    )


def format_metrics_table(metrics: Mapping[str, ArrangementMetrics]) -> str:
    """Return one named profile per row, with all metrics and three-decimal floats."""
    names = [field.name for field in fields(ArrangementMetrics)]
    rows = [["Profile", *names]]
    for name, values in metrics.items():
        row = [name.title()]
        for field_name in names:
            value = getattr(values, field_name)
            row.append(str(value) if isinstance(value, int) else f"{value:.3f}")
        rows.append(row)
    widths = [max(len(row[index]) for row in rows) for index in range(len(rows[0]))]

    def render(row: list[str]) -> str:
        return " | ".join(value.ljust(width) for value, width in zip(row, widths, strict=True)).rstrip()

    return "\n".join([render(rows[0]), "-+-".join("-" * width for width in widths), *(render(row) for row in rows[1:])])


def _ratio(numerator: float, denominator: float) -> float:
    return numerator / denominator if denominator else 0.0


def _mean(values: list[float]) -> float:
    return _ratio(fsum(values), len(values))


def _p95(values: list[float]) -> float:
    return sorted(values)[ceil(0.95 * len(values)) - 1] if values else 0.0


__all__ = ["ArrangementMetrics", "calculate_metrics", "format_metrics_table"]
