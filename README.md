# PianoFold

> Where songs unfold into piano.

**PianoFold** is a local AI workspace that turns an audio recording into
playable piano arrangements. Bring in a song, then receive three versions of
the arrangement—Simple, Standard, and Rich—along with printable sheet music,
MIDI, and in-browser playback.

Your audio is processed on your own machine. PianoFold is built for the
moment when a recording becomes something you can put beneath your hands.

## What it does

- Accepts **MP3, WAV, M4A, and FLAC** recordings.
- Transcribes audio locally with MuScriptor-small on Apple Silicon.
- Creates three playable piano arrangements for different levels of comfort.
- Displays MusicXML sheet music in the browser.
- Plays the original recording and the generated piano MIDI independently.
- Exports MIDI and MusicXML for every arrangement.
- Keeps a project progress record and provides a deterministic arrangement
  complexity and fidelity report.

## Requirements

- macOS on Apple Silicon with **MPS** available.
- Python **3.12** and [uv](https://docs.astral.sh/uv/).
- Node.js and npm.
- A Hugging Face account with access to the
  [MuScriptor-small model](https://huggingface.co/MuScriptor/muscriptor-small).

PianoFold deliberately does not fall back to CPU transcription. If MPS is not
available, it will explain the problem instead of silently running much more
slowly.

## Quick start

Clone the project and install its two local parts:

```bash
git clone https://github.com/zhaiziqi/PianoFold.git
cd PianoFold
uv sync
cd apps/web && npm ci && cd ../..
```

Accept the MuScriptor-small model terms on Hugging Face, then sign in once:

```bash
uvx hf auth login
```

Start the API in one terminal:

```bash
uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
```

Start the workspace in another:

```bash
cd apps/web
npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open [http://127.0.0.1:3000](http://127.0.0.1:3000), choose a song, and keep
the page open while the arrangement is prepared. On this machine, a three-and-
a-half-minute MP3 has taken about two minutes from upload to completed exports.
The first run may take longer while the model loads.

## Your workspace

Once processing finishes, choose **Simple**, **Standard**, or **Rich** to:

1. Read the generated score directly in the browser.
2. Listen to the original recording or the piano MIDI preview.
3. Download the selected arrangement as MIDI or MusicXML.

The project ID displayed in the workspace can be used to inspect the saved
arrangement metrics:

```bash
uv run python scripts/evaluate_project.py <project_id>
```

This reads the existing project data and prints a comparison table; it does not
run a new transcription or change any project files.

## Development

Run the API checks:

```bash
uv run pytest -q
```

Run the web checks:

```bash
cd apps/web
npm test -- --run
npm run build
npm run lint
```

## Notes on local data

Uploaded recordings and generated projects are stored only in the local
`data/` directory. They are ignored by Git so a personal recording, MIDI file,
or score cannot be accidentally included in a commit.

For a complete manual test flow, see the
[local workspace acceptance checklist](docs/acceptance/local-workspace.md).
