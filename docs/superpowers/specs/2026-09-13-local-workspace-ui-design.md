# PianoFold Local Workspace UI and Metrics Design

## Scope

This phase turns the completed local project API into a browser-usable
single-page workspace and adds a local CLI report of arrangement metrics. It
includes audio upload, durable processing status, Simple/Standard/Rich score
switching, MusicXML notation display, independent original-audio and piano
MIDI playback, and artifact downloads.

It does not add accounts, a database, a remote queue, waveform rendering,
perfect audio/MIDI synchronization, score-following cursors, PDF export,
server-side rendering of notation, advanced engraving, sidebars, marketing
pages, or cloud deployment.

## User Experience

The one-page workspace uses a warm ivory canvas, dark graphite type, restrained
rules, and a music-sheet feel. It has three states:

1. **Ready:** a short PianoFold introduction and a clear dropzone/button for
   MP3, WAV, M4A, or FLAC.
2. **Processing:** the submitted file name, current stage label, concise
   progress bar, and a readable failure message if the persisted API status
   becomes `failed`.
3. **Ready to play:** the song name, a three-way difficulty selector, score,
   independent original and piano controls, and downloads for the selected
   difficulty.

The browser starts at the Ready state. A successful upload receives an ID,
then the page polls `GET /api/projects/{id}` every second while status is
`uploaded` or `processing`. It stops polling at `done` or `failed`, and it
cleans up the timer if the page component unmounts or the user uploads another
file. Reload recovery is intentionally out of scope: no project ID is stored
in browser storage for this MVP.

## Frontend Architecture

`apps/web/app/page.tsx` becomes a small client-side coordinator; it holds the
selected file, project metadata, selected difficulty, and user-visible error.
Focused components keep imperative browser libraries isolated:

```text
components/
  upload-dropzone.tsx        file selection and drag/drop validation
  processing-status.tsx      persisted stage, progress, failed state
  difficulty-selector.tsx    Simple / Standard / Rich controls
  score-viewer.tsx           client-only OpenSheetMusicDisplay lifecycle
  audio-player.tsx           native HTMLAudioElement controls
  midi-player.tsx            client-only Tone.js + @tonejs/midi scheduling
  download-actions.tsx       selected profile artifact links
lib/
  api.ts                     typed project HTTP calls and endpoint builders
  project.ts                 shared frontend types and fixed difficulty values
```

No component assumes a filesystem path. `lib/api.ts` only creates requests to
the existing fixed API routes. At development time the Next.js server rewrites
`/api/*` to `http://127.0.0.1:8000/api/*`; deployment remains out of scope.

## Score Rendering

The score viewer dynamically imports `opensheetmusicdisplay` inside a browser
effect, never during server rendering. On a completed project or difficulty
change it fetches the selected `musicxml` endpoint as text, creates/updates an
SVG-backed renderer in its own container, then loads and renders the result.
It clears obsolete notation before rerendering and displays a local fallback
message if fetching or rendering fails. It uses the existing backend-produced
MusicXML without invoking transcription or arrangement.

## Playback

Original audio uses a native `<audio controls>` element pointed at
`/api/projects/{id}/audio`; the browser provides play, pause, seek, volume,
and format support.

Piano playback dynamically imports `tone` and `@tonejs/midi` after a user
click. The click calls `Tone.start()`, fetches the selected MIDI bytes,
parses them with `Midi.fromUrl` or equivalent fetched byte parsing, schedules
note starts/stops through Tone's transport with a simple polyphonic synth, and
offers Stop/Restart. It disposes the synth, clears transport events, and stops
the transport when the selected difficulty changes or the component unmounts.
No sample downloads, waveform, synchronizing behavior, or score cursor is
included.

## Metrics

`pianofold/evaluation/metrics.py` calculates one deterministic
`ArrangementMetrics` for a source ScoreIR and PianoArrangement. It includes:

- note count and notes per second;
- mean and 95th-percentile left/right onset-center leap;
- maximum simultaneous left/right span;
- mean onset polyphony;
- hand crossing and span-violation counts;
- salient source-note, melody-anchor, bass-anchor retention; and
- pitch-class coverage.

`scripts/evaluate_project.py <project_id>` loads the persisted ScoreIR plus
all three MIDI-independent arrangements recreated from that ScoreIR and
prints a Simple/Standard/Rich comparison table. It does not run MuScriptor or
modify project artifacts. Calculations use the same role analysis and
salience definitions as the arranger; no desired gradient is hard-coded.

## Testing

- Add Vitest plus React Testing Library for pure client behavior: API endpoint
  construction, upload validation/form submission, stage rendering, difficulty
  switching, and selected artifact links. Mock OpenSheetMusicDisplay, Tone,
  and native media in component tests rather than running audio hardware.
- Add Python unit tests for every metric using compact synthetic ScoreIR and
  arrangements, including hand crossing, spans, percentile behavior, and
  traceable retention.
- Add a CLI test using a temporary project fixture to assert all three table
  headings and profile rows; no model inference.
- Run `uv run pytest -q`, `cd apps/web && npm test`, `npm run build`, and
  `npm run lint`. Perform one manual browser smoke run against the existing
  local API and a real short audio file.

## Success Criteria

A local user can open the web app, submit a supported audio file, observe real
persisted processing progress, switch instantly among all three completed
versions, read the selected piano score, play either original audio or the
selected piano MIDI, and download its MIDI/MusicXML. Independently, the
metrics CLI reports real complexity and fidelity measurements for all three
profiles of an existing project.
