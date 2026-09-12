# PianoFold Local MVP — Milestone A Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:executing-plans` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and verify the Apple-Silicon local pipeline: audio → MuScriptor small → provider-independent ScoreIR → quantized baseline piano reduction → deterministic MIDI.

**Architecture:** FastAPI owns only a health endpoint in this scope. A MuScriptor adapter converts its event stream directly into ScoreIR; quantization, reduction, and export depend only on ScoreIR/PianoArrangement and never model-specific types.

**Tech Stack:** Python 3.12, uv, FastAPI, Pydantic, pytest, mido, pretty_midi, librosa, numpy, scipy, MuScriptor small on PyTorch MPS float16; Next.js, React, TypeScript, Tailwind CSS.

**Spec:** User-approved PianoFold Local MVP brief, 2026-09-13; this plan implements only Tasks 1–5 and stops at Milestone A.

## Global Constraints

- Target macOS Apple Silicon; model is exactly `small`, device `mps`, dtype `float16`. Never silently fall back to CPU.
- Python is `>=3.12,<3.13`; use uv. Do not commit model weights or `data/projects`.
- Tests must use synthetic events/ScoreIR and never load a model unless marked `model`.
- ScoreIR ordering is `(start, pitch, instrument, id)`; all results are deterministic.
- Do not start role analysis, salience, profiles, Beam Search, MusicXML, project API routes, or Web UI before the user accepts Milestone A.

## Planned File Structure

- `apps/api/main.py`, `apps/api/routes/health.py`: application and health transport.
- `apps/web/`: bootstrap-only Next.js/Tailwind page.
- `pianofold/transcription/{base,muscriptor}.py`: protocol, error types, lazy MuScriptor adapter, event conversion.
- `pianofold/symbolic/{models,serialize,quantize}.py`: validated JSON ScoreIR and grid snapping.
- `pianofold/arrangement/baseline.py`: slice-based non-drum two-hand reduction.
- `pianofold/export/midi.py`: deterministic type-1 MIDI writer.
- `scripts/{smoke_transcribe,inspect_score,smoke_arrange}.py`: independent diagnostics.
- `tests/{api,symbolic,transcription,arrangement,export}/`: unit coverage for every layer.

---

### Task 1: Bootstrap the local environment

**Files:**
- Create: `.gitignore`, `.env.example`, `README.md`, `pyproject.toml`, `apps/api/main.py`, `apps/api/routes/health.py`, `tests/api/test_health.py`, and a minimal `apps/web` Next.js TypeScript/Tailwind project.
- Create directories: `pianofold/{transcription,symbolic,analysis,arrangement,export,evaluation}`, `tests/{symbolic,analysis,arrangement,api}`, `scripts`, `examples`, `data/projects`.

**Interfaces:**
- Produces `app: FastAPI` in `apps.api.main`.
- Produces `GET /health → {"status": "ok"}`.

- [ ] **Step 1: Initialise Git and local-data ignores**

Run:

```bash
git init
git branch -M main
```

Ignore `.venv/`, `__pycache__/`, `.pytest_cache/`, `.env`, `.DS_Store`, `node_modules/`, `.next/`, and `data/projects/`; retain `data/.gitkeep`.

- [ ] **Step 2: Write the failing route test**

```python
from fastapi.testclient import TestClient
from apps.api.main import app

def test_health_returns_ok() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}
```

- [ ] **Step 3: Verify failure**

Run: `uv run pytest tests/api/test_health.py -v`

Expected: collection fails because `apps.api.main` does not exist.

- [ ] **Step 4: Implement the minimum backend**

Set Python `>=3.12,<3.13`. Add FastAPI, uvicorn, python-multipart, Pydantic, mido, pretty_midi, music21, librosa, numpy, scipy, MuScriptor, pytest, pytest-asyncio, and httpx. Configure `testpaths = ["tests"]` and register the `model` marker. Implement:

```python
router = APIRouter()

@router.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

Include it from `FastAPI(title="PianoFold")`.

- [ ] **Step 5: Implement only the frontend bootstrap**

The root page renders:

```tsx
<main>
  <h1>PianoFold</h1>
  <p>Local AI Piano Arranger</p>
</main>
```

Provide `dev`, `build`, `lint`, and `test` package scripts.

- [ ] **Step 6: Verify and commit**

Run `uv run pytest`; run `uv run uvicorn apps.api.main:app --port 8000` and verify `curl http://127.0.0.1:8000/health`; run `npm run build` in `apps/web`. Commit:

```bash
git add .
git commit -m "chore: bootstrap PianoFold local development environment"
```

### Task 2: Integrate a deliberate MuScriptor-small smoke command

**Files:**
- Create: `pianofold/transcription/base.py`, `pianofold/transcription/muscriptor.py`, `scripts/smoke_transcribe.py`, `tests/transcription/test_muscriptor_config.py`.
- Modify: `pyproject.toml`, `README.md`.

**Interfaces:**
- Produces `class Transcriber(Protocol): def transcribe(self, audio_path: Path) -> ScoreIR`.
- Produces `MuScriptorTranscriber.MODEL_SIZE == "small"`.
- Produces `uv run python scripts/smoke_transcribe.py INPUT`, writing `data/smoke/transcription.mid`.

- [ ] **Step 1: Write the failing configuration test**

```python
from pianofold.transcription.muscriptor import MuScriptorTranscriber

def test_muscriptor_is_pinned_to_small_mps_float16() -> None:
    transcriber = MuScriptorTranscriber()
    assert transcriber.MODEL_SIZE == "small"
    assert transcriber.device == "mps"
    assert transcriber.dtype == "float16"
```

- [ ] **Step 2: Confirm failure and add the lazy adapter**

Run `uv run pytest tests/transcription/test_muscriptor_config.py -v`; expect import failure. Keep all model imports/construction in `muscriptor.py`; create the model only on first transcription, after `torch.backends.mps.is_available()` succeeds. Inspect the installed official package signature and adapt its `TranscriptionModel` API only in this module, always passing small/MPS/float16.

- [ ] **Step 3: Implement explicit errors and metrics**

For unavailable weights/authentication, raise `MuScriptorUnavailableError` containing:

```text
MuScriptor weights are not available.
Accept the MuScriptor model license on Hugging Face and run:
uvx hf auth login
```

Do not fallback to CPU. The script validates input, writes model MIDI, and prints device, model, audio duration, inference seconds, RTF (`seconds / duration`), and output path.

- [ ] **Step 4: Verify and commit**

Run the configuration test without model loading. With user-provided 15–30 second audio plus accepted HF licence, run `uv run python scripts/smoke_transcribe.py /absolute/path/song.wav` and verify the MIDI opens. Commit:

```bash
git add pianofold/transcription scripts/smoke_transcribe.py tests/transcription pyproject.toml README.md
git commit -m "feat: integrate MuScriptor small transcription"
```

### Task 3: Add ScoreIR and direct event conversion

**Files:**
- Create: `pianofold/symbolic/models.py`, `pianofold/symbolic/serialize.py`, `tests/symbolic/test_models.py`, `tests/transcription/test_events_to_score_ir.py`, `scripts/inspect_score.py`.
- Modify: `pianofold/transcription/muscriptor.py`.

**Interfaces:**
- Produces frozen `Note(id, pitch, start, end, instrument, velocity=80)`, plus `TempoChange` and `ScoreIR`.
- Produces `events_to_score_ir(events) -> ScoreIR`, `TranscriptionParseError`, and deterministic JSON read/write.

- [ ] **Step 1: Write validation, ordering, JSON, and event-pairing tests**

Tests reject pitch outside 0–127, start below zero, end not after start, and velocity outside 1–127. Assert notes sort by `(start, pitch, instrument, id)`; JSON round-trip is stable. Use fake local start/end/progress event types to test normal pairs, overlapping same-pitch notes, two instruments, ignored progress, out-of-order end events, computed duration, unmatched end, and missing end:

```python
def test_missing_end_raises_parse_error() -> None:
    events = [NoteStartEvent(pitch=60, time=0.0, instrument="piano")]
    with pytest.raises(TranscriptionParseError, match="missing end"):
        events_to_score_ir(events)
```

- [ ] **Step 2: Confirm failure then minimally implement**

Run `uv run pytest tests/symbolic tests/transcription/test_events_to_score_ir.py -v`; expect missing modules. Pair active starts FIFO by `(instrument, pitch)`, assign completed notes `{instrument}:{index}`, preserve default velocity 80, raise on unmatched/missing ends, and never parse generated MIDI to make ScoreIR. `score_ir.json` uses sorted-key JSON.

- [ ] **Step 3: Add inspection and commit**

`inspect_score.py FILE` prints note count, instruments, pitch range (or `n/a`), duration, and per-instrument counts. Run the same test command expecting PASS, then commit:

```bash
git add pianofold/symbolic pianofold/transcription/muscriptor.py scripts/inspect_score.py tests
git commit -m "feat: add provider-independent ScoreIR"
```

### Task 4: Quantize globally to an explicit note grid

**Files:**
- Create: `pianofold/symbolic/quantize.py`, `tests/symbolic/test_quantize.py`.

**Interfaces:**
- Produces `quantize_score(score: ScoreIR, bpm: float, subdivision: int = 4) -> ScoreIR`.

- [ ] **Step 1: Write failing timing tests**

At 120 BPM/subdivision 4, assert 0.13–0.39 snaps to 0.125–0.375. Assert a 0.12–0.13 note is lengthened to one 0.125-second grid step. Cover subdivisions 1/2/4, invalid BPM/subdivision, overlap preservation, and repeatability.

- [ ] **Step 2: Confirm failure and implement**

Run `uv run pytest tests/symbolic/test_quantize.py -v`; expect missing import. Compute `step = 60 / bpm / subdivision`; accept only finite positive BPM and 1, 2, or 4 subdivisions. Use Decimal/integer tick arithmetic to snap boundaries, then force end to `start + step` when required. Preserve note attributes/tempo changes and recalculate duration.

- [ ] **Step 3: Verify and commit**

Run the test file expecting PASS. Commit:

```bash
git add pianofold/symbolic/quantize.py tests/symbolic/test_quantize.py
git commit -m "feat: add symbolic timing quantization"
```

### Task 5: Produce a deterministic naive two-hand MIDI

**Files:**
- Create: `pianofold/arrangement/baseline.py`, `pianofold/export/midi.py`, `tests/arrangement/test_baseline.py`, `tests/export/test_midi.py`, `scripts/smoke_arrange.py`.
- Modify: `pianofold/symbolic/models.py`, `README.md`.

**Interfaces:**
- Produces `PianoNote(pitch, start, end, hand, source_note_ids)`, `PianoArrangement(notes, difficulty)`.
- Produces `baseline_reduce(score: ScoreIR) -> PianoArrangement`.
- Produces `arrangement_to_midi(arrangement, output_path, bpm=120.0) -> Path`.

- [ ] **Step 1: Write failing reduction and MIDI tests**

Use simultaneous synthetic notes to prove `drum`/ `drums` are omitted; pitches ≥60 are RH, lower pitches LH; every slice retains highest RH/lowest LH; RH count ≤3 and LH count ≤2; timing/source IDs survive; order repeats exactly. Test exported type-1 MIDI has `Right Hand` and `Left Hand` tracks, program 0, velocity 80, expected pitches/counts, and timing within one tick.

- [ ] **Step 2: Confirm failure and implement reduction**

Run `uv run pytest tests/arrangement/test_baseline.py tests/export/test_midi.py -v`; expect missing modules. Group by equal quantized start, omit case-insensitive drum instruments, choose LH candidates by `(pitch, id)` and RH by `(-pitch, id)`, retain first two/three respectively, set `difficulty="baseline"`, and sort output `(start, pitch, hand, source_note_ids)`.

- [ ] **Step 3: Implement MIDI writer and smoke arrange command**

Write a type-1 MIDI with a tempo track and named RH/LH tracks. Emit program 0, with note-off before note-on at an equal tick and pitch-ascending tie order. `smoke_arrange.py SCORE_IR_JSON OUTPUT_MID --bpm 120` loads JSON, quantizes, reduces, exports, and prints source/arrangement counts plus path.

- [ ] **Step 4: Verify the full real pipeline, commit, and stop**

Run unit tests, then the real audio run: smoke transcribe → event ScoreIR + `score_ir.json` → inspect → quantize/reduce → `baseline.mid`; audibly verify it opens. Record Mac model, Python/PyTorch/MuScriptor versions, MPS/small status, input duration, inference seconds, RTF, transcription note count, instruments, baseline note count, paths, and all test results. Commit:

```bash
git add pianofold scripts tests README.md
git commit -m "feat: complete first audio-to-piano pipeline"
```

Stop at Milestone A and report the actual generated files. Do not proceed to post-Milestone-A tasks until the user approves.

## Plan Self-Review

- **Coverage:** Bootstrap, MuScriptor small smoke use, direct ScoreIR conversion, quantization, naive reduction, two-track MIDI, tests, and the mandatory real-device checkpoint all have a dedicated task.
- **Scope:** Explicitly excludes every post-Milestone-A capability.
- **Type consistency:** The provider returns ScoreIR; reduction returns PianoArrangement; export consumes PianoArrangement.

