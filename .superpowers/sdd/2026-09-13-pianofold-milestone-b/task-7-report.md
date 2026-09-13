# Task 7 Report: symbolic note salience

## Scope

Implemented only the Task 7 salience API in `pianofold/arrangement/salience.py` and synthetic behavioral tests in `tests/arrangement/test_salience.py`. No candidate generation, difficulty profiles, or beam-search code was added.

## TDD evidence

1. Added three tests before production implementation.
2. Ran `uv run pytest tests/arrangement/test_salience.py -v` with the implementation absent. Collection failed with the expected `ModuleNotFoundError: No module named 'pianofold.arrangement.salience'`.
3. Added the minimal implementation.
4. Re-ran the focused suite: **3 passed**.
5. Ran the complete suite: **60 passed**, with two pre-existing dependency deprecation warnings.

## Implementation details

- `SalienceWeights` is an immutable slotted dataclass with the required defaults: melody `0.45`, harmony `0.20`, duration `0.15`, rhythm `0.10`, continuity `0.10`.
- `note_salience` combines exactly those five weighted components:
  - melody and harmony from the ID-keyed `RoleAnalysis` maps;
  - duration normalized by the longest note duration in the score;
  - rhythm based on onset-slice cardinality, with melody/bass anchors receiving the highest value;
  - continuity based on immediately adjacent notes of the same instrument, rewarding pitch gaps through five semitones.
- The combined result is clamped to `[0, 1]` at the public output boundary; no intermediate rounding is performed.
- `score_salience` returns a deterministic ID-keyed dictionary in canonical `ScoreIR` note order.
- Invalid negative, non-finite, or all-zero custom weight sets raise `ValueError`.

## Concerns

The brief specifies the component concepts but not a single numeric sub-formula for rhythm and continuity. The implementation uses reciprocal onset cardinality for non-anchors and a linear `1 - gap / 5` continuity contribution, both deterministic and bounded.
