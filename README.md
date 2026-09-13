# PianoFold

Local AI Piano Arranger.

## Local workspace

PianoFold's local workspace accepts one MP3, WAV, M4A, or FLAC recording,
processes it on this machine, and produces Simple, Standard, and Rich piano
arrangements. Keep the API and web app running in separate terminals from the
repository root:

```bash
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

```bash
cd apps/web && npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000), choose a supported short
audio file, and leave the page open while the local transcription and
arrangement job completes. The page shows the persisted stages and progress,
then offers all three difficulty versions, their MusicXML scores, independent
original-audio and piano-preview controls, and MIDI/MusicXML downloads for the
currently selected version.

For a completed project's deterministic complexity and fidelity report, copy
the project ID shown in the workspace and run:

```bash
uv run python scripts/evaluate_project.py <project_id>
```

The command reads the saved `score_ir.json` and prints a Simple/Standard/Rich
comparison table; it does not transcribe audio or modify any project files.

See [the local acceptance checklist](docs/acceptance/local-workspace.md) for
the complete upload, processing, score, playback, download, and metrics
workflow.

## Development

Run the full API checks with `uv run pytest -q`. Run the web checks with
`cd apps/web && npm test -- --run && npm run build && npm run lint`.

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
