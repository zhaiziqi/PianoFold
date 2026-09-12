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

It uses only MuScriptor-small on `mps` with `float16`, writes
`data/smoke/transcription.mid`, and prints duration, inference time, and RTF.
It intentionally fails when MPS is unavailable rather than falling back to
CPU.
