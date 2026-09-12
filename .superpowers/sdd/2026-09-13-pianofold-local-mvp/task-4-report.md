# Task 4 report: deterministic ScoreIR quantization

## Result

Implemented `quantize_score(score: ScoreIR, bpm: float, subdivision: int = 4) -> ScoreIR` in `pianofold/symbolic/quantize.py`.

The implementation computes the global step as `60 / bpm / subdivision`, accepts only finite positive BPM values and integer subdivisions 1, 2, or 4, snaps note boundaries using deterministic Decimal arithmetic, and lengthens any collapsed/zero-length quantized note to one grid step. Note identity, pitch, instrument, velocity, overlaps, and tempo-change objects are preserved; output ordering and duration are provided by `ScoreIR`.

## TDD evidence

### RED

Added the focused synthetic tests in `tests/symbolic/test_quantize.py`, then ran:

```text
uv run pytest tests/symbolic/test_quantize.py -v
```

The suite failed during collection with the expected missing-feature error:

```text
ModuleNotFoundError: No module named 'pianofold.symbolic.quantize'
```

### GREEN

After implementing the production module:

```text
uv run pytest tests/symbolic/test_quantize.py -v
```

Result: `16 passed`.

Full regression suite:

```text
uv run pytest -q
```

Result: `37 passed, 2 warnings` (the warnings are existing Starlette/httpx and anyio deprecations).

## Tests added

- Nearest-grid snapping at 120 BPM / subdivision 4 (`0.13–0.39` to `0.125–0.375`).
- Minimum one-step duration for a `0.12–0.13` note.
- Supported subdivisions 1, 2, and 4.
- Invalid BPM values: zero, negative, infinity, and NaN.
- Invalid subdivisions.
- Attribute, overlap, and tempo-change preservation.
- Repeatability.

## Self-review

- Timing calculations use a high-precision local Decimal context and explicit half-up behavior for nonnegative times.
- Inputs are not mutated; a new `ScoreIR` and new `Note` values are returned.
- `Note` validation guarantees no output note has `end <= start`.
- Scope is limited to quantization; no tempo detection, provider changes, reduction, or later features were added.

## Concerns

- Tempo changes remain at their original times by design; this task requires preserving them but does not define quantizing tempo anchors.
- Decimal conversion is based on `str()` representations of input floats, which is deterministic and avoids binary floating-point drift; extremely unusual BPM values may still produce large decimal outputs, though the local precision is ample for normal score timings.
