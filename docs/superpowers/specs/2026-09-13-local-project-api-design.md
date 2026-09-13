# PianoFold Local Project API Design

## Scope

This design implements the first backend-facing product slice after the
completed arrangement engine: MusicXML export, a local per-project processing
pipeline, and FastAPI endpoints that a later web workspace will call. It does
not implement the web UI, score rendering, playback, evaluation metrics,
databases, remote queues, user accounts, or PDF export.

## Goals

- Accept one local MP3, WAV, M4A, or FLAC upload and immediately return a
  project identifier.
- Process it locally with MuScriptor small on MPS, producing retained
  intermediate artifacts plus Simple, Standard, and Rich MIDI and MusicXML.
- Persist observable project status, stage, progress, and error detail in a
  JSON metadata file so status survives a server restart.
- Serve only files belonging to the requested valid project and fixed
  difficulty profile.
- Keep ordinary tests deterministic and model-free through a `Transcriber`
  dependency supplied to the pipeline.

## Architecture

`PianoFoldPipeline` owns one project directory and is the only component that
creates processing artifacts. It receives a `Transcriber` protocol
implementation, writes initial metadata before processing, and updates the
same file as it advances through `transcribing`, `analyzing`, `arranging`, and
`exporting`. On success it writes `done`; on every handled exception it writes
`failed` and a non-empty error message. A project with a failure is therefore
explicitly failed rather than silently resembling a finished project.

The FastAPI route layer owns request validation, initial upload persistence,
background-task scheduling, and safe artifact responses. It creates a fresh
pipeline for each submitted project through an application-owned factory. The
factory constructs `MuScriptorTranscriber` lazily inside background work, not
when a route module imports or the application starts.

`arrangement_to_musicxml` is an independent deterministic export boundary. It
uses music21 to create a two-part piano score: right hand in treble clef and
left hand in bass clef. It preserves the arrangement's note pitches, hand,
and timing at the existing 120 BPM pipeline tempo. First-version engraving is
intentionally basic; no fingerings, pedal, dynamics, ornaments, or PDF are in
scope.

## Project Files

Each project is stored beneath the configured root (default
`data/projects`) as `<project_id>/`:

```text
input.<original-extension>
transcription.mid
score_ir.json
simple.mid
standard.mid
rich.mid
simple.musicxml
standard.musicxml
rich.musicxml
metadata.json
```

The identifier is a generated UUID4 string. APIs accept only canonical UUID
text; they never concatenate arbitrary client-provided paths. Difficulty is
validated against exactly `simple`, `standard`, and `rich`. The upload route
uses the supplied filename only to select one lower-case extension from
`.mp3`, `.wav`, `.m4a`, or `.flac`; it never uses that filename as a path.

`metadata.json` always contains these fields:

```json
{
  "project_id": "uuid",
  "status": "uploaded | processing | done | failed",
  "stage": "uploaded | transcribing | analyzing | arranging | exporting | done | failed",
  "progress": 0.0,
  "error": null,
  "duration": null,
  "model": "muscriptor-small",
  "device": "mps",
  "profiles": ["simple", "standard", "rich"]
}
```

`duration` becomes the quantized score duration on successful processing.
`error` remains `null` except in the failed state. The pipeline writes the
metadata atomically through a sibling temporary file and replacement, so a
status query never parses a half-written document.

## Processing Flow

1. The upload route writes the audio into a new project directory and writes
   `uploaded` metadata.
2. A FastAPI `BackgroundTasks` task marks it `processing/transcribing`, uses
   `transcribe_with_midi` when the configured transcriber supplies it (the
   MuScriptor adapter), otherwise calls `transcribe`, and writes available raw
   transcription MIDI plus `score_ir.json`.
3. It quantizes ScoreIR at 120 BPM and records the `analyzing` stage. Role and
   salience analysis remains internal to the deterministic arranger.
4. It marks `arranging`, computes all three arrangements from the same
   quantized ScoreIR, then marks `exporting` and writes each MIDI and
   MusicXML file.
5. It records `done` with progress `1.0` only after every expected export
   exists. Any exception writes `failed`; successful-looking metadata is not
   left behind with missing output files.

The earlier standalone smoke scripts remain available; this pipeline is an
additional application boundary, not a replacement for diagnostic CLI use.

## HTTP Contract

| Endpoint | Success result | Failure behavior |
| --- | --- | --- |
| `POST /api/projects` multipart field `audio` | `202`, `{project_id, status: "processing"}` | `400` for missing or unsupported audio |
| `GET /api/projects/{id}` | current metadata JSON | `404` for unknown or malformed project ID |
| `GET /api/projects/{id}/audio` | original file response | `404` if absent or project unknown |
| `GET /api/projects/{id}/arrangements/{difficulty}/midi` | named MIDI file response | `404` until that valid artifact exists; `404` for invalid id/difficulty |
| `GET /api/projects/{id}/arrangements/{difficulty}/musicxml` | named MusicXML file response | same validation and readiness semantics as MIDI |

No processing endpoint accepts a server filesystem path. Background work is
local and single-user only: no Celery, Redis, RQ, database, or distributed
job semantics are introduced.

## Error Handling

Unsupported extension, empty upload, unreadable input, empty transcription,
MusicXML export failure, and transcription errors are user-visible through
the project metadata failed state. Route error messages do not expose paths
outside the project root. Download requests made before an export is ready
receive a normal 404 rather than an empty or partial response.

## Testing and Verification

- Unit-test MusicXML output for a readable two-hand grand staff with expected
  pitches and clefs.
- Unit-test the pipeline with a fake `Transcriber` and synthetic `ScoreIR`:
  expected files, metadata transitions, all profiles, and explicit failed
  metadata after a synthetic error.
- API-test multipart validation, asynchronous submission/status behavior,
  artifact retrieval, and traversal-resistant invalid identifiers and
  difficulties. Override the application pipeline factory with a fake for
  every ordinary test.
- Run `uv run pytest -q`, then run the existing frontend production build as
  a no-regression check. Real MuScriptor inference remains a manual smoke
  check only.

## Success Criteria

Given a supported audio upload, a browser client can receive a project ID,
poll a persisted status document, and retrieve the original audio plus all
three generated MIDI and MusicXML artifacts after completion. The project
directory retains every listed intermediate file, and invalid IDs,
difficulties, filenames, and file paths cannot access files outside that
directory.
