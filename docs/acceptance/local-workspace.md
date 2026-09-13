# Local workspace acceptance

This checklist validates the local PianoFold journey without changing project
data. It applies to a completed project created by the API in the current
working tree.

## Prerequisites

- Run the commands from the repository root in two separate terminals:

  ```bash
  uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000
  ```

  ```bash
  cd apps/web && npm run dev -- --hostname 127.0.0.1 --port 3000
  ```

- Open `http://127.0.0.1:3000`.
- Have a short local MP3, WAV, M4A, or FLAC recording available. A real
  `data/smoke/input.mp3` is the conventional smoke input when it exists in the
  current working tree. Do not use a file or persisted project from another
  checkout as acceptance evidence.

## Manual journey

1. Confirm the opening page shows the PianoFold introduction and the “Choose a
   song” upload action with the supported-format hint.
2. Choose or drop the supported audio file. Confirm its name appears, then
   “Uploading your song…” and “Checking your arrangement…” appear as
   applicable.
3. Observe the persisted processing card. It should progress through the
   readable Transcribing, Analyzing, Arranging, and Exporting labels before
   completion. If the job fails, the card must show the persisted error rather
   than a ready-to-play section.
4. On success, record the visible project ID and confirm “Ready to play.”
   Select **Simple**, **Standard**, and **Rich** in turn. Each selection must
   update the selected radio option, both download targets, and the displayed
   MusicXML score. Verify each score visibly renders rather than showing “The
   score could not be displayed.”
5. For each selected difficulty, follow **Download MIDI** and **Download
   MusicXML**. Confirm the browser receives the respective selected artifact.
6. Use the browser's native **Original recording** player independently: start,
   pause, seek, and adjust volume where the browser exposes those controls.
   Then press **Play piano**, confirm the selected arrangement enters playback,
   press **Stop piano**, and use **Restart piano**. Changing difficulty must
   stop/reset the piano preview; it must not alter the original-recording
   player.
7. In a third terminal, run the metrics report with the recorded identifier:

   ```bash
   uv run python scripts/evaluate_project.py <project_id>
   ```

   Confirm the output contains the Simple, Standard, and Rich rows and the
   arrangement metrics columns. This command is read-only; it must not cause
   new processing or alter downloaded artifacts.

## Automated verification

Run the full suite after the manual check:

```bash
uv run pytest -q && (cd apps/web && npm test -- --run && npm run build && npm run lint) && git diff --check
```

Expected result: all Python and frontend tests pass, the production frontend
build succeeds, and lint has no errors. The repository currently emits two
known anonymous-default-export lint warnings and a non-failing Vite
native-config-loader notice.

## Recorded run — 2026-09-13

- Workspace: `/Users/zhaiziqi/Piano_project/.worktrees/local-workspace-ui`
  on branch `codex/local-workspace-ui`.
- Automated command: `uv run pytest -q && (cd apps/web && npm test -- --run &&
  npm run build && npm run lint) && git diff --check`.
- Result: 221 Python tests passed; 56 frontend tests passed; the Next.js build
  completed; lint reported 0 errors and the two known warnings above;
  `git diff --check` passed.
- Endpoint arrangement: ports 8000 and 3000 were already occupied by
  non-worktree processes and were left untouched. The isolated API was started
  from this worktree at `http://127.0.0.1:8010`; the isolated web app was
  started at `http://127.0.0.1:3010`. Its development rewrite is intentionally
  fixed to port 8000, so the 3010 page cannot submit to the isolated 8010 API
  without a configuration change, which is outside this documentation-only
  task.
- Browser result: the in-app browser visibly loaded the 3010 ready state:
  PianoFold heading and introduction, supported-format hint, and “Choose a
  song” button were present. The original 3000 navigation timed out and
  remained `about:blank`. The UI's upload/processing/done controls were not
  used, because doing so would send the source file to the unrelated 8000 API.
- Source and project: controller-authorized read-only source
  `/Users/zhaiziqi/Piano_project/data/smoke/input.mp3`; isolated API project
  `d3f5fe88-dea3-4972-8114-d202be676dbd`. The API received the file at 8010
  and created all new artifacts only under this worktree's
  `data/projects/d3f5fe88-dea3-4972-8114-d202be676dbd/`.
- Processing evidence: persisted metadata was observed at
  `processing/transcribing` (10%), `processing/arranging` (55%), and
  `processing/exporting` (75%), then `done/done` (100%) with duration 35.125
  seconds and no error. The short analyzing stage was not captured between
  polls.
- Artifact evidence: the original audio plus both MIDI and MusicXML endpoints
  for Simple, Standard, and Rich each returned HTTP 200 from the isolated API.
  `uv run python scripts/evaluate_project.py
  d3f5fe88-dea3-4972-8114-d202be676dbd` printed all three profile rows and
  metrics columns without writing project artifacts.
- Remaining manual browser gate: after the 8000/3000 process owners release
  those ports (or the development API target becomes configurable), repeat
  steps 2–6 through one connected workspace. Confirm all three rendered scores
  and downloaded artifacts, original-audio controls, and Play/Stop/Restart
  piano controls. Browser tooling can inspect and operate controls, but cannot
  establish that audible sound reached a listener; audible output always
  requires a human listening check.
