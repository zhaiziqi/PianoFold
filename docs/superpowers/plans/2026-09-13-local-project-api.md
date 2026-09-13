# PianoFold Local Project API Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Let a local client upload one supported audio file, process it into Simple/Standard/Rich MIDI and MusicXML artifacts, poll durable status, and download only validated project files.

**Architecture:** A deterministic MusicXML exporter turns each `PianoArrangement` into a two-staff piano score. `PianoFoldPipeline` owns one project directory, atomically persists metadata through every stage, and receives a `Transcriber` dependency for model-free tests. FastAPI validates uploads and identifiers, schedules the pipeline with `BackgroundTasks`, and serves only fixed artifact names rooted beneath the configured project directory.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, music21, mido, pytest, pytest-asyncio, HTTPX/TestClient.

**Spec:** `docs/superpowers/specs/2026-09-13-local-project-api-design.md`

## Global Constraints

- Target is macOS Apple Silicon; real production transcription remains MuScriptor `small` on MPS with `float16`.
- Ordinary tests must use synthetic ScoreIR and fake transcribers; no normal test downloads or loads a model.
- Keep MuScriptor types out of arrangement, export, project metadata, and route modules.
- Supported uploads are only `.mp3`, `.wav`, `.m4a`, and `.flac`; never trust the provided filename as a path.
- Project IDs must be canonical UUID4 text; profile names must be exactly `simple`, `standard`, or `rich` after API validation.
- Persist `input.*`, `transcription.mid`, `score_ir.json`, all three MIDI/MusicXML outputs, and atomic `metadata.json` under `data/projects/<id>/`.
- Metadata status is one of `uploaded`, `processing`, `done`, `failed`; stage is one of `uploaded`, `transcribing`, `analyzing`, `arranging`, `exporting`, `done`, `failed`.
- On any processing failure write explicit `failed` metadata with a non-empty error; do not leave a project appearing successful with absent exports.
- Do not add databases, user accounts, Redis/Celery/RQ, cloud services, PDF export, frontend UI, score rendering, playback, or evaluation metrics.
- Preserve existing CLI smoke scripts and the current MIDI export behavior.

---

### Task 1: Deterministic two-staff MusicXML export

**Files:**
- Create: `pianofold/export/musicxml.py`
- Modify: `pianofold/export/__init__.py`
- Create: `tests/export/test_musicxml.py`

**Interfaces:**
- Consumes: `pianofold.symbolic.models.PianoArrangement` and `PianoNote`.
- Produces: `arrangement_to_musicxml(arrangement: PianoArrangement, output_path: Path, bpm: float = 120.0) -> Path`.
- Later tasks call this function for every profile-specific arrangement.

- [ ] **Step 1: Write failing exporter tests**

```python
def test_musicxml_export_writes_two_piano_staves_with_note_timing(tmp_path: Path) -> None:
    arrangement = PianoArrangement(
        (
            PianoNote(43, 0.0, 0.5, "left", ("bass",)),
            PianoNote(60, 0.0, 1.0, "right", ("melody",)),
        ),
        "standard",
    )
    output = arrangement_to_musicxml(arrangement, tmp_path / "standard.musicxml", 120.0)

    parsed = converter.parse(output)
    assert output.is_file()
    assert [note.pitch.midi for note in parsed.parts[0].recurse().notes] == [60]
    assert [note.pitch.midi for note in parsed.parts[1].recurse().notes] == [43]
    assert isinstance(parsed.parts[0].recurse().getElementsByClass(clef.Clef)[0], clef.TrebleClef)
    assert isinstance(parsed.parts[1].recurse().getElementsByClass(clef.Clef)[0], clef.BassClef)
```

Add a separate test that rejects non-positive/non-finite BPM and a test that rejects an output path whose parent does not exist.

- [ ] **Step 2: Run the new tests to verify they fail**

Run: `uv run pytest tests/export/test_musicxml.py -q`

Expected: FAIL because `pianofold.export.musicxml` and `arrangement_to_musicxml` do not exist.

- [ ] **Step 3: Implement minimal MusicXML export**

```python
def arrangement_to_musicxml(
    arrangement: PianoArrangement, output_path: Path, bpm: float = 120.0
) -> Path:
    _validate_bpm_and_parent(bpm, output_path)
    score = stream.Score()
    right, left = stream.PartStaff(), stream.PartStaff()
    right.insert(0, clef.TrebleClef())
    left.insert(0, clef.BassClef())
    for piano_note in arrangement.notes:
        part = right if piano_note.hand == "right" else left
        exported = note.Note(piano_note.pitch)
        exported.offset = seconds_to_quarter_length(piano_note.start, bpm)
        exported.duration.quarterLength = seconds_to_quarter_length(
            piano_note.end - piano_note.start, bpm
        )
        part.insert(exported.offset, exported)
    score.insert(0, tempo.MetronomeMark(number=bpm))
    score.insert(0, right)
    score.insert(0, left)
    score.write("musicxml", fp=output_path)
    return output_path
```

Use a `layout.StaffGroup` with piano bracket/group symbol so rendered output is a grand staff. Keep output ordering deterministic by iterating the already ordered arrangement notes.

- [ ] **Step 4: Run exporter and full regression tests**

Run: `uv run pytest tests/export/test_musicxml.py tests/export/test_midi.py -q`

Expected: PASS; parsed output has two named piano staves, fixed note pitches/offsets/durations, and valid clefs.

- [ ] **Step 5: Commit**

```bash
git add pianofold/export/musicxml.py pianofold/export/__init__.py tests/export/test_musicxml.py
git commit -m "feat: export piano arrangements as MusicXML"
```

### Task 2: Durable local processing pipeline

**Files:**
- Create: `pianofold/projects/__init__.py`
- Create: `pianofold/projects/models.py`
- Create: `pianofold/projects/metadata.py`
- Create: `pianofold/projects/pipeline.py`
- Create: `tests/projects/test_pipeline.py`

**Interfaces:**
- Consumes: `Transcriber`, `ScoreIR`, `quantize_score`, `arrange`, the three exported profiles, `arrangement_to_midi`, and `arrangement_to_musicxml`.
- Produces: `ProjectMetadata`, `ProjectResult`, `create_project_metadata(project_id: str)`, `read_metadata(project_dir: Path)`, `write_metadata(project_dir: Path, metadata: ProjectMetadata)`, and `PianoFoldPipeline(transcriber: Transcriber).process(audio_path: Path, project_dir: Path) -> ProjectResult`.
- Later route task calls metadata helpers and a pipeline factory.

- [ ] **Step 1: Write failing pipeline tests with a fake transcriber**

```python
class FakeTranscriber:
    def transcribe(self, audio_path: Path) -> ScoreIR:
        return ScoreIR((
            Note("bass", 43, 0.0, 1.0, "bass"),
            Note("melody", 67, 0.0, 1.0, "piano"),
        ))

def test_pipeline_writes_every_declared_artifact_and_done_metadata(tmp_path: Path) -> None:
    project_dir = tmp_path / "project"
    project_dir.mkdir()
    audio = project_dir / "input.wav"
    audio.write_bytes(b"fake audio")

    result = PianoFoldPipeline(FakeTranscriber()).process(audio, project_dir)

    assert result.metadata.status == "done"
    assert result.metadata.stage == "done"
    assert result.metadata.progress == 1.0
    assert {path.name for path in project_dir.iterdir()} >= {
        "input.wav", "score_ir.json", "simple.mid", "standard.mid", "rich.mid",
        "simple.musicxml", "standard.musicxml", "rich.musicxml", "metadata.json",
    }
```

Add tests that (a) metadata is valid JSON after every write, (b) a fake transcriber exception creates `failed` metadata with a non-empty error, (c) no arrangement output exists before a failed transcription, and (d) a fake that supplies `transcribe_with_midi` persists `transcription.mid` verbatim.

- [ ] **Step 2: Run pipeline tests to verify they fail**

Run: `uv run pytest tests/projects/test_pipeline.py -q`

Expected: FAIL because the projects package and pipeline interfaces do not exist.

- [ ] **Step 3: Implement immutable metadata and atomic persistence**

```python
@dataclass(frozen=True, slots=True)
class ProjectMetadata:
    project_id: str
    status: Literal["uploaded", "processing", "done", "failed"]
    stage: Literal["uploaded", "transcribing", "analyzing", "arranging", "exporting", "done", "failed"]
    progress: float
    error: str | None
    duration: float | None
    model: str = "muscriptor-small"
    device: str = "mps"
    profiles: tuple[str, ...] = ("simple", "standard", "rich")

def write_metadata(project_dir: Path, metadata: ProjectMetadata) -> Path:
    destination = project_dir / "metadata.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(asdict(metadata), sort_keys=True), encoding="utf-8")
    temporary.replace(destination)
    return destination
```

Validate canonical UUID text, finite `0.0 <= progress <= 1.0`, status/stage combinations, and non-empty error only for failed metadata. `read_metadata` returns the dataclass from JSON rather than an untyped dict.

- [ ] **Step 4: Implement `PianoFoldPipeline.process`**

```python
def process(self, audio_path: Path, project_dir: Path) -> ProjectResult:
    metadata = self._set_state(project_dir, "processing", "transcribing", 0.1)
    try:
        score, midi_bytes = self._transcribe(audio_path)
        if not score.notes:
            raise ValueError("Transcription produced no notes")
        if midi_bytes is not None:
            (project_dir / "transcription.mid").write_bytes(midi_bytes)
        write_score(score, project_dir / "score_ir.json")
        quantized = quantize_score(score, 120.0)
        self._set_state(project_dir, "processing", "analyzing", 0.35)
        arrangements = {profile.name: arrange(quantized, profile) for profile in PROFILES}
        self._set_state(project_dir, "processing", "arranging", 0.65)
        for name, arrangement in arrangements.items():
            arrangement_to_midi(arrangement, project_dir / f"{name}.mid", 120.0)
            arrangement_to_musicxml(arrangement, project_dir / f"{name}.musicxml", 120.0)
        return self._set_done(project_dir, quantized.duration)
    except Exception as error:
        return self._set_failed(project_dir, error)
```

Create the initial uploaded metadata before processing. Use a small private
helper to detect the optional `transcribe_with_midi` method structurally; do
not import MuScriptor into this package. Confirm every required output exists
before writing `done`.

- [ ] **Step 5: Run pipeline tests and full regression suite**

Run: `uv run pytest tests/projects/test_pipeline.py -q && uv run pytest -q`

Expected: PASS; no model marker is required and all prior symbolic/export/API tests remain green.

- [ ] **Step 6: Commit**

```bash
git add pianofold/projects tests/projects/test_pipeline.py
git commit -m "feat: add complete local PianoFold processing pipeline"
```

### Task 3: Safe local project HTTP API

**Files:**
- Create: `apps/api/routes/projects.py`
- Modify: `apps/api/main.py`
- Create: `tests/api/test_projects.py`

**Interfaces:**
- Consumes: `ProjectMetadata`, metadata readers/writers, `PianoFoldPipeline`, and the three fixed profile names.
- Produces: `POST /api/projects`, `GET /api/projects/{project_id}`, `GET /api/projects/{project_id}/audio`, `GET /api/projects/{project_id}/arrangements/{difficulty}/midi`, and `GET /api/projects/{project_id}/arrangements/{difficulty}/musicxml`.
- The future web UI consumes only these HTTP interfaces.

- [ ] **Step 1: Write failing API tests using an injected fake pipeline factory**

```python
def test_upload_returns_project_id_then_status_and_artifacts(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    client = configured_client(tmp_path, FakeTranscriber())

    response = client.post(
        "/api/projects",
        files={"audio": ("song.wav", b"audio", "audio/wav")},
    )

    assert response.status_code == 202
    project_id = response.json()["project_id"]
    assert response.json()["status"] == "processing"
    assert client.get(f"/api/projects/{project_id}").json()["status"] == "done"
    assert client.get(f"/api/projects/{project_id}/arrangements/simple/midi").status_code == 200
    assert client.get(f"/api/projects/{project_id}/arrangements/rich/musicxml").status_code == 200
    assert client.get(f"/api/projects/{project_id}/audio").content == b"audio"
```

Add isolated tests for unsupported and extension-less files (`400`), empty
uploads (`400`), malformed/unknown UUIDs (`404`), invalid difficulty (`404`),
not-ready artifact (`404`), and traversal strings such as `../metadata.json`
or `simple/../../audio` (`404`).

- [ ] **Step 2: Run API tests to verify they fail**

Run: `uv run pytest tests/api/test_projects.py -q`

Expected: FAIL because the project router and endpoints do not exist.

- [ ] **Step 3: Implement route-local validation and application configuration**

```python
PROJECT_ROOT = Path("data/projects")
ALLOWED_EXTENSIONS = {".mp3", ".wav", ".m4a", ".flac"}
DIFFICULTIES = frozenset({"simple", "standard", "rich"})

def canonical_project_id(value: str) -> str:
    parsed = UUID(value)
    if str(parsed) != value:
        raise HTTPException(status_code=404, detail="Project not found")
    return value

@router.post("/api/projects", status_code=status.HTTP_202_ACCEPTED)
async def create_project(audio: UploadFile, background_tasks: BackgroundTasks, request: Request) -> dict[str, str]:
    extension = validated_extension(audio.filename)
    body = await audio.read()
    if not body:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    project_id = str(uuid4())
    project_dir = project_root(request) / project_id
    project_dir.mkdir(parents=True)
    input_path = project_dir / f"input{extension}"
    input_path.write_bytes(body)
    write_metadata(project_dir, create_project_metadata(project_id))
    background_tasks.add_task(pipeline_factory(request)().process, input_path, project_dir)
    return {"project_id": project_id, "status": "processing"}
```

In `apps.api.main`, create `app.state.project_root` and a lazy
`app.state.pipeline_factory` that builds `PianoFoldPipeline(MuScriptorTranscriber())`.
Tests override both state values. File responses resolve only the known
project directory and fixed generated filename; use a shared lookup helper
that raises `404` before returning `FileResponse`.

- [ ] **Step 4: Run API, pipeline, and whole-suite tests**

Run: `uv run pytest tests/api/test_projects.py tests/projects/test_pipeline.py -q && uv run pytest -q && (cd apps/web && npm run build && npm run lint) && git diff --check`

Expected: PASS; route tests do not initialize MuScriptor, invalid paths never
produce a response outside the temporary project root, the health route still
returns `{"status": "ok"}`, the unchanged frontend builds, and lint reports
no errors (its two existing anonymous-default-export warnings are allowed).

- [ ] **Step 5: Commit**

```bash
git add apps/api/main.py apps/api/routes/projects.py tests/api/test_projects.py
git commit -m "feat: expose local PianoFold processing API"
```

## Plan Self-Review

- Spec coverage: Task 1 implements the MusicXML contract; Task 2 implements
  project artifacts, metadata lifecycle, atomic writes, all profile exports,
  and failed state; Task 3 implements every specified HTTP endpoint and its
  path-safety rules. Existing smoke scripts remain the diagnostic CLI path,
  as required by the approved design.
- Scope: no task adds frontend, score renderer, playback, PDF, metric system,
  database, cloud service, authentication, or queue.
- Interface consistency: all later code receives `ProjectMetadata`,
  `PianoFoldPipeline.process(audio_path, project_dir)`, and the single
  `arrangement_to_musicxml` export defined by earlier tasks.
- Placeholder scan: no incomplete tasks or unspecified validation behavior
  remain; each production task includes concrete failing tests, commands,
  implementation boundaries, and a commit.
