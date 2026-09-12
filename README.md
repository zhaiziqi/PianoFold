# PianoFold

Local AI Piano Arranger.

## Development

Run the API checks with `uv run pytest`.

Start the API with `uv run uvicorn apps.api.main:app --port 8000`.

Start the web application with `cd apps/web && npm run dev`.

## MuScriptor smoke transcription

On an Apple Silicon Mac with MPS available, accept the MuScriptor-small model
license on Hugging Face and authenticate once:

```bash
uvx hf auth login
```

Then run a deliberate real-audio smoke check (a 15–30 second WAV is a useful
starting point):

```bash
uv run python scripts/smoke_transcribe.py /absolute/path/song.wav
```

It uses only MuScriptor-small on `mps` with `float16`, writing both
`data/smoke/transcription.mid` and the direct-event-derived
`data/smoke/score_ir.json`. It prints duration plus a transcription-call total
and RTF; those measures may include lazy model loading, so they are not
presented as pure inference timing. It intentionally fails when MPS is
unavailable rather than falling back to CPU.

## Baseline piano arrangement

Inspect the transcription score, then create the deterministic two-hand
baseline MIDI with:

```bash
uv run python scripts/inspect_score.py data/smoke/score_ir.json
```

```bash
uv run python scripts/smoke_arrange.py data/smoke/score_ir.json data/smoke/baseline.mid --bpm 120
```

The command quantizes the score, omits `drum`/`drums` instruments, and writes
a type-1 MIDI with `Right Hand` and `Left Hand` General MIDI piano tracks.
