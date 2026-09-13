# Task 8 report: difficulty profiles

## Delivered

- Added frozen `DifficultyProfile` with positive finite validation for all limits and weights.
- Added `SIMPLE`, `STANDARD`, and `RICH` presets with the specified hand polyphony and span limits.
- Added case-insensitive, whitespace-tolerant `profile_for` lookup with `ValueError` for unknown names.
- Added synthetic tests covering preset ordering, lookup behavior, immutability, and invalid construction values.

## Verification

- `uv run pytest tests/arrangement/test_profiles.py -v`: 12 passed.
- `uv run pytest -q`: 73 passed (two pre-existing dependency deprecation warnings).

## Concerns

The brief specifies relative heuristic weight behavior but no exact numeric weight values. The presets use monotonic values that satisfy those constraints: Simple `(leap, span, density, fidelity) = (1.5, 1.5, 2.0, 0.75)`, Standard `(1.0, 1.0, 1.0, 1.0)`, and Rich `(0.5, 0.5, 0.5, 1.25)`.
