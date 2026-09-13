# PianoFold Local Workspace UI and Metrics Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Provide a browser-usable local PianoFold workspace with upload, durable progress, MusicXML display, three difficulty versions, independent audio/MIDI playback and downloads, plus deterministic arrangement metrics.

**Architecture:** Python metrics read persisted ScoreIR and reconstruct the same three deterministic arrangements without model inference. A Next.js client page talks only to the existing `/api/projects` routes; focused client components isolate upload, status, difficulty, notation, native audio, Tone/MIDI, and downloads. Browser-only music libraries load dynamically in effects or user-event handlers to keep Next.js server rendering safe.

**Tech Stack:** Python 3.12, pytest, FastAPI project API, Next.js 15, React 19, TypeScript, Tailwind CSS, Vitest, React Testing Library, OpenSheetMusicDisplay, Tone.js, @tonejs/midi.

**Spec:** `docs/superpowers/specs/2026-09-13-local-workspace-ui-design.md`

## Global Constraints

- Keep the backend API contract unchanged: uploads and artifacts use only `/api/projects` and its fixed profile routes.
- UI supports `.mp3`, `.wav`, `.m4a`, and `.flac`; never displays a local filesystem path.
- Poll status only while `uploaded` or `processing`, every 1000 ms; cancel timers on terminal status, replacement upload, or unmount.
- Difficulty is exactly `simple`, `standard`, or `rich`; changing it requests only existing output artifacts and never reruns arranging.
- Use a warm ivory background, dark graphite text, spare editorial/music-sheet layout; no AI gradients, sidebar, login, dashboard, waveform, or marketing page.
- Original audio uses native browser controls. MIDI playback uses Tone only after an explicit user gesture; it remains independent of the audio player.
- Dynamically import OpenSheetMusicDisplay, Tone, and @tonejs/midi from client-only code; dispose/clear player resources on difficulty changes and unmount.
- Metrics must calculate actual values from source ScoreIR and arrangement data; do not hard-code expected Simple/Standard/Rich trends.
- Ordinary Python and frontend tests must not run MuScriptor, network requests, hardware audio, or a real browser.
- Do not add PDF export, sync/cursor playback, user accounts, database, queue, cloud features, or advanced engraving.

---

### Task 1: Deterministic arrangement metrics and local report CLI

**Files:**
- Create: `pianofold/evaluation/metrics.py`
- Create: `scripts/evaluate_project.py`
- Create: `tests/evaluation/test_metrics.py`
- Create: `tests/evaluation/test_evaluate_project.py`

**Interfaces:**
- Consumes: `ScoreIR`, `PianoArrangement`, `RoleAnalysis`, `score_salience`, `analyze_roles`, and existing profile constraints.
- Produces: frozen `ArrangementMetrics`, `calculate_metrics(source: ScoreIR, arrangement: PianoArrangement) -> ArrangementMetrics`, and `format_metrics_table(metrics: Mapping[str, ArrangementMetrics]) -> str`.
- The CLI recreates arrangements through `arrange(quantize_score(read_score(...), 120.0), profile)` and prints the three profile rows without writing files.

- [ ] **Step 1: Write failing metric tests**

```python
def test_metrics_calculate_hand_movement_span_crossing_and_retention() -> None:
    source = ScoreIR((
        Note("bass", 43, 0.0, 0.5, "bass"),
        Note("melody", 67, 0.0, 0.5, "piano"),
        Note("harmony", 59, 0.5, 1.0, "piano"),
    ))
    arrangement = PianoArrangement((
        PianoNote(43, 0.0, 0.5, "left", ("bass",)),
        PianoNote(67, 0.0, 0.5, "right", ("melody",)),
        PianoNote(59, 0.5, 1.0, "left", ("harmony",)),
    ), "standard")

    metrics = calculate_metrics(source, arrangement)

    assert metrics.note_count == 3
    assert metrics.hand_crossing_count == 0
    assert metrics.max_lh_span == 0
    assert metrics.melody_anchor_retention == 1.0
    assert metrics.bass_anchor_retention == 1.0
```

Add discrete fixtures that prove 95th-percentile selection, crossing detection,
span violations against the profile matching `arrangement.difficulty`, and
source ID/salient/pitch-class retention. Add a CLI test creating a temporary
project with `score_ir.json` and asserting `Simple`, `Standard`, and `Rich`
table rows.

- [ ] **Step 2: Run tests to verify RED**

Run: `uv run pytest tests/evaluation/test_metrics.py tests/evaluation/test_evaluate_project.py -q`

Expected: FAIL because metrics module and CLI do not exist.

- [ ] **Step 3: Implement immutable metrics and report formatting**

```python
@dataclass(frozen=True, slots=True)
class ArrangementMetrics:
    note_count: int
    notes_per_second: float
    mean_lh_leap: float
    mean_rh_leap: float
    p95_lh_leap: float
    p95_rh_leap: float
    max_lh_span: int
    max_rh_span: int
    mean_polyphony: float
    hand_crossing_count: int
    span_violation_count: int
    salient_retention: float
    melody_anchor_retention: float
    bass_anchor_retention: float
    pitch_class_coverage: float
```

Group notes by exact onset. For each hand, calculate onset centers in ascending
time order and absolute adjacent-center differences; p95 uses a documented
nearest-rank index. Count a crossing only where simultaneous LH and RH notes
overlap in pitch. Calculate source retention from `source_note_ids`, current
`analyze_roles`, and `score_salience`; zero denominators return `0.0`.

- [ ] **Step 4: Implement the read-only CLI**

```python
parser.add_argument("project_id")
project_dir = project_root / canonical_uuid(args.project_id)
score = quantize_score(read_score(project_dir / "score_ir.json"), 120.0)
metrics = {
    profile.name: calculate_metrics(score, arrange(score, profile))
    for profile in (SIMPLE, STANDARD, RICH)
}
print(format_metrics_table(metrics))
```

Validate the UUID and required `score_ir.json`; print a clear nonzero-exit
error for an unknown project. Do not invoke MuScriptor or overwrite any
artifact.

- [ ] **Step 5: Run focused and full Python tests**

Run: `uv run pytest tests/evaluation/test_metrics.py tests/evaluation/test_evaluate_project.py -q && uv run pytest -q`

Expected: PASS; CLI reports all profiles and all existing tests stay green.

- [ ] **Step 6: Commit**

```bash
git add pianofold/evaluation/metrics.py scripts/evaluate_project.py tests/evaluation
git commit -m "feat: add arrangement metrics report"
```

### Task 2: Frontend test foundation and typed local API client

**Files:**
- Modify: `apps/web/package.json`
- Modify: `apps/web/package-lock.json`
- Create: `apps/web/vitest.config.ts`
- Create: `apps/web/test/setup.ts`
- Create: `apps/web/lib/project.ts`
- Create: `apps/web/lib/api.ts`
- Create: `apps/web/lib/api.test.ts`
- Modify: `apps/web/next.config.ts`

**Interfaces:**
- Consumes: the established project API response fields and fixed route names.
- Produces: `Difficulty`, `ProjectStatus`, `ProjectMetadata`, `PROJECT_STAGES`, `uploadProject(file)`, `getProject(id)`, and safe route builders for audio/MIDI/MusicXML.
- Later UI components import only these frontend types/functions.

- [ ] **Step 1: Write failing API-client tests**

```tsx
it("posts audio and returns the submitted project", async () => {
  vi.stubGlobal("fetch", vi.fn().mockResolvedValue(jsonResponse({
    project_id: "11111111-1111-4111-8111-111111111111", status: "processing",
  })));

  await expect(uploadProject(new File(["audio"], "song.wav", { type: "audio/wav" })))
    .resolves.toEqual({ project_id: "11111111-1111-4111-8111-111111111111", status: "processing" });
  expect(fetch).toHaveBeenCalledWith("/api/projects", expect.objectContaining({ method: "POST" }));
});

it("builds only fixed selected-profile artifact routes", () => {
  expect(musicxmlUrl(PROJECT_ID, "rich")).toBe(`/api/projects/${PROJECT_ID}/arrangements/rich/musicxml`);
});
```

Add tests converting API failures to a readable `ApiError` and rejecting a
frontend-only invalid difficulty without constructing a route.

- [ ] **Step 2: Run the test to verify RED**

Run: `cd apps/web && npm test -- --run lib/api.test.ts`

Expected: FAIL because Vitest configuration and API modules do not exist.

- [ ] **Step 3: Install and configure frontend dependencies**

```bash
npm install opensheetmusicdisplay tone @tonejs/midi
npm install --save-dev vitest @vitejs/plugin-react jsdom @testing-library/react @testing-library/jest-dom
```

Configure Vitest with `environment: "jsdom"`, the React plugin, a setup file
importing `@testing-library/jest-dom/vitest`, and `test` script `vitest`.
Add a Next.js development rewrite from `/api/:path*` to
`http://127.0.0.1:8000/api/:path*`; do not rewrite production deployment
behavior beyond that local target.

- [ ] **Step 4: Implement typed routes and requests**

```ts
export const DIFFICULTIES = ["simple", "standard", "rich"] as const;
export type Difficulty = (typeof DIFFICULTIES)[number];

export async function uploadProject(file: File): Promise<ProjectSubmission> {
  const data = new FormData();
  data.append("audio", file);
  return request("/api/projects", { method: "POST", body: data });
}

export function midiUrl(projectId: string, difficulty: Difficulty): string {
  return `/api/projects/${projectId}/arrangements/${difficulty}/midi`;
}
```

Use `encodeURIComponent` for the project ID, fixed suffixes, and status-aware
error parsing. Do not use paths supplied by server metadata or user filenames.

- [ ] **Step 5: Run unit tests, build, and lint**

Run: `cd apps/web && npm test -- --run && npm run build && npm run lint`

Expected: tests pass, production compilation succeeds, and lint reports no
errors (the existing two anonymous-default-export warnings remain allowed).

- [ ] **Step 6: Commit**

```bash
git add apps/web/package.json apps/web/package-lock.json apps/web/vitest.config.ts apps/web/test apps/web/lib apps/web/next.config.ts
git commit -m "feat: add typed local project API client"
```

### Task 3: Upload, status, difficulty, and download workspace components

**Files:**
- Create: `apps/web/components/upload-dropzone.tsx`
- Create: `apps/web/components/processing-status.tsx`
- Create: `apps/web/components/difficulty-selector.tsx`
- Create: `apps/web/components/download-actions.tsx`
- Create: `apps/web/components/workspace.test.tsx`
- Modify: `apps/web/app/page.tsx`
- Modify: `apps/web/app/globals.css`

**Interfaces:**
- Consumes: `uploadProject`, `getProject`, URL builders, `Difficulty`, and `ProjectMetadata` from Task 2.
- Produces: the complete ready/processing/done/failed visual state and selected difficulty state for Tasks 4–5.
- Later score/player components receive only `projectId` and `difficulty` when status is `done`.

- [ ] **Step 1: Write failing component tests**

```tsx
it("submits a supported dropped file and polls until done", async () => {
  render(<Home />);
  await userEvent.upload(screen.getByLabelText(/choose a song/i), wavFile);

  expect(await screen.findByText(/transcribing/i)).toBeInTheDocument();
  await waitFor(() => expect(screen.getByRole("heading", { name: /arrangement/i })).toBeInTheDocument());
});

it("switches the selected difficulty and updates both download links", async () => {
  renderDoneWorkspace();
  await userEvent.click(screen.getByRole("radio", { name: /rich/i }));

  expect(screen.getByRole("link", { name: /download midi/i })).toHaveAttribute("href", expect.stringContaining("/rich/midi"));
  expect(screen.getByRole("link", { name: /download musicxml/i })).toHaveAttribute("href", expect.stringContaining("/rich/musicxml"));
});
```

Mock `lib/api`; use fake timers to advance polling; assert rejected extension
shows a local message and no upload call. Add a failed-status test asserting
the API error text is visible and no score/player region is rendered.

- [ ] **Step 2: Run component tests to verify RED**

Run: `cd apps/web && npm test -- --run components/workspace.test.tsx`

Expected: FAIL because the components and client workspace do not exist.

- [ ] **Step 3: Implement focused visual components and page state**

```tsx
const [project, setProject] = useState<ProjectMetadata | null>(null);
const [difficulty, setDifficulty] = useState<Difficulty>("standard");

useEffect(() => {
  if (!project || !["uploaded", "processing"].includes(project.status)) return;
  const timer = window.setInterval(async () => setProject(await getProject(project.project_id)), 1000);
  return () => window.clearInterval(timer);
}, [project?.project_id, project?.status]);
```

The dropzone accepts pointer/file-picker and drag/drop interaction, validates
extension before calling the API, and labels its input for keyboard access.
`ProcessingStatus` maps each stable API stage to readable copy and renders
`progress * 100` in an ARIA progress bar. The difficulty selector uses radio
buttons. Downloads are simple accessible anchors; only render once `done`.

Style the page with one centered paper-like column, thin rules, responsive
spacing, visible focus states, and no visual framework beyond existing
Tailwind/global CSS.

- [ ] **Step 4: Run component tests, build, and lint**

Run: `cd apps/web && npm test -- --run components/workspace.test.tsx && npm run build && npm run lint`

Expected: ready, processing, failure, done, selector, and download behavior
pass; build and lint report no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web/app apps/web/components
git commit -m "feat: add local PianoFold workspace UI"
```

### Task 4: Client-only score rendering and independent playback

**Files:**
- Create: `apps/web/components/score-viewer.tsx`
- Create: `apps/web/components/audio-player.tsx`
- Create: `apps/web/components/midi-player.tsx`
- Create: `apps/web/components/media.test.tsx`
- Modify: `apps/web/app/page.tsx`

**Interfaces:**
- Consumes: completed `projectId`, selected `Difficulty`, and Task 2 URL builders.
- Produces: rendered selected MusicXML, native original-audio control, and
  user-gesture-started selected MIDI player.

- [ ] **Step 1: Write failing media tests**

```tsx
it("loads the newly selected MusicXML and renders it after dynamic import", async () => {
  render(<ScoreViewer projectId={PROJECT_ID} difficulty="simple" />);
  expect(await screen.findByLabelText(/piano score/i)).toBeInTheDocument();
  rerender(<ScoreViewer projectId={PROJECT_ID} difficulty="rich" />);
  await waitFor(() => expect(mockLoad).toHaveBeenLastCalledWith(expect.stringContaining("/rich/musicxml")));
});

it("does not initialize Tone until the piano play button is clicked", async () => {
  render(<MidiPlayer projectId={PROJECT_ID} difficulty="standard" />);
  expect(mockToneStart).not.toHaveBeenCalled();
  await userEvent.click(screen.getByRole("button", { name: /play piano/i }));
  expect(mockToneStart).toHaveBeenCalledOnce();
});
```

Mock dynamic imports for OpenSheetMusicDisplay, Tone, and @tonejs/midi. Add
tests that cleanup runs on difficulty change/unmount, score-render failures
display a fallback, and native audio points at the audio endpoint.

- [ ] **Step 2: Run tests to verify RED**

Run: `cd apps/web && npm test -- --run components/media.test.tsx`

Expected: FAIL because viewer/player components do not exist.

- [ ] **Step 3: Implement browser-only notation and players**

```tsx
useEffect(() => {
  let active = true;
  void import("opensheetmusicdisplay").then(async ({ OpenSheetMusicDisplay }) => {
    const renderer = new OpenSheetMusicDisplay(container.current!, { backend: "svg", autoResize: true });
    await renderer.load(musicxmlUrl(projectId, difficulty));
    if (active) renderer.render();
  }).catch(() => active && setError("The score could not be displayed."));
  return () => { active = false; container.current?.replaceChildren(); };
}, [projectId, difficulty]);
```

`AudioPlayer` renders only a labelled `<audio controls src={audioUrl(projectId)}>`.
`MidiPlayer` dynamically imports dependencies inside `play`, calls
`await Tone.start()`, fetches/parses the selected MIDI, schedules notes with a
`PolySynth`, and exposes Stop/Restart. Its cleanup clears scheduled events,
stops/cancels transport, and disposes audio objects. Render these components
in the done workspace below downloads; keep playback controls separate.

- [ ] **Step 4: Run media tests and frontend verification**

Run: `cd apps/web && npm test -- --run components/media.test.tsx && npm test -- --run && npm run build && npm run lint`

Expected: dynamic-library mocks validate lifecycle behavior; the full frontend
suite, production build, and lint have no errors.

- [ ] **Step 5: Commit**

```bash
git add apps/web/components/score-viewer.tsx apps/web/components/audio-player.tsx apps/web/components/midi-player.tsx apps/web/components/media.test.tsx apps/web/app/page.tsx
git commit -m "feat: render scores and add arrangement playback"
```

### Task 5: End-to-end local acceptance and README workflow

**Files:**
- Modify: `README.md`
- Create: `docs/acceptance/local-workspace.md`

**Interfaces:**
- Consumes: API launch command, frontend dev command, actual supported audio,
  project API, web workspace, and metrics CLI.
- Produces: reproducible manual acceptance steps; no production interface changes.

- [ ] **Step 1: Write the manual acceptance checklist**

Document exact steps to start API and frontend in separate terminals, upload a
short local audio file, confirm every processing stage, switch all three
difficulties, render each score, operate native audio and piano controls,
download both selected artifacts, and run `scripts/evaluate_project.py`.

- [ ] **Step 2: Run final automated verification**

Run: `uv run pytest -q && (cd apps/web && npm test -- --run && npm run build && npm run lint) && git diff --check`

Expected: all Python/frontend tests pass, build succeeds, and lint has no
errors (only the established two anonymous-default-export warnings if still
present).

- [ ] **Step 3: Perform the local browser acceptance run**

Start API: `uv run uvicorn apps.api.main:app --host 127.0.0.1 --port 8000`

Start web: `cd apps/web && npm run dev -- --hostname 127.0.0.1 --port 3000`

Use an existing real project or upload `data/smoke/input.mp3`. Confirm visual
states, all three score switches, two independent playback controls, downloads,
and metrics CLI output. Record actual project ID and any non-blocking browser
limitation in `docs/acceptance/local-workspace.md`.

- [ ] **Step 4: Commit**

```bash
git add README.md docs/acceptance/local-workspace.md
git commit -m "docs: add local workspace acceptance workflow"
```

## Plan Self-Review

- Spec coverage: Task 1 implements every requested metric and read-only CLI;
  Task 2 establishes browser test/dependency/API foundation; Task 3 implements
  ready/processing/done/failed workspace, upload, polling, selection, and
  downloads; Task 4 provides client-only notation and independent playback;
  Task 5 validates the local user journey.
- Interface consistency: all frontend consumers use the typed API client from
  Task 2; all metric calculations consume existing symbolic types and reuse
  existing role/salience/profile interfaces.
- Scope: none of the tasks add synchronization, waveforms, PDF, remote
  execution, accounts, databases, or advanced notation.
- Placeholder scan: each task names exact files, test behaviors, commands,
  production interfaces, and a commit.
