# PianoFold Difficulty-Aware Arrangement — Milestone B Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `superpowers:subagent-driven-development` to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the baseline pitch split with deterministic, difficulty-aware two-hand piano arrangements that trade source fidelity against playability across Simple, Standard, and Rich profiles.

**Architecture:** Every analysis function consumes only ScoreIR and returns deterministic, ID-keyed symbolic data. Candidate generation works slice-by-slice under profile hard limits; Beam Search selects the highest cumulative fidelity-minus-playability route using backpointers, then converts chosen Voicings into the existing PianoArrangement domain model.

**Tech Stack:** Python 3.12, pytest, dataclasses, standard-library itertools/math/statistics; existing ScoreIR, PianoArrangement, quantization, and MIDI exporter.

**Spec:** User-approved PianoFold Local MVP brief, 2026-09-13, Tasks 6–12 (original task attachment); this plan is the Milestone B execution companion to `docs/superpowers/plans/2026-09-13-pianofold-local-mvp.md`.

## Global Constraints

- The transcription adapter remains isolated: analysis and arrangement code must import ScoreIR types only, never MuScriptor.
- All algorithms must be deterministic for identical ScoreIR and DifficultyProfile input.
- Unit tests use hand-authored ScoreIR fixtures, not model inference or downloaded audio.
- Do not introduce chord-name detection, machine-learned role classifiers, random velocity, deep perceptual/audio similarity, MusicXML, API project routes, or Web UI.
- Keep all salience weights in one immutable dataclass; do not scatter score magic numbers.
- Candidate count is at most 32 per time slice and preselection is at most eight source notes.
- Simple/Standard/Rich parameters are heuristics, not ergonomic standards.
- Stop after Milestone B; do not start Task 13+ without user approval.

---

### Task 6: Add deterministic role analysis

**Files:**
- Create: `pianofold/analysis/models.py`, `pianofold/analysis/melody.py`, `pianofold/analysis/bass.py`, `pianofold/analysis/harmony.py`, `tests/analysis/test_roles.py`
- Modify: `pianofold/analysis/__init__.py`

**Interfaces:**
- Produces `RoleAnalysis(melody: Mapping[str, float], bass: Mapping[str, float], harmony: Mapping[str, float], melody_anchors: frozenset[str], bass_anchors: frozenset[str])`.
- Produces `score_melody_probability(note: Note, context: ScoreIR) -> float`, `score_bass_probability(note: Note, context: ScoreIR) -> float`, and `analyze_roles(score: ScoreIR) -> RoleAnalysis`.

- [ ] **Step 1: Write the failing role tests**

Use a synthetic score with an upper sustained vocal/piano line, low bass notes, and same-onset chord tones. Assert every score is in `[0, 1]`; upper sustained notes score higher for melody than redundant middle tones; low/bass-labelled notes score higher for bass; melody and bass anchors are deterministic; harmonic importance rewards distinct pitch classes and discounts doubled notes.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/analysis/test_roles.py -v`

Expected: FAIL because the role-analysis modules and `RoleAnalysis` do not exist.

- [ ] **Step 3: Implement the domain result and heuristics**

Create frozen `RoleAnalysis` with immutable mappings. Clamp all component scores to `[0, 1]`. Melody combines normalized pitch, normalized duration, previous/next same-instrument contour continuity, vocal-name token, same-instrument neighbors, and an explicit low-pitch penalty. Bass combines inverse normalized pitch, bass-name token, beat-local lowest-note membership, and duration. Harmony calculates each non-anchor note's pitch-class rarity inside its onset slice, assigning lower value to repeated pitch classes. Select one highest melody score and one highest bass score per onset slice as anchors with stable `id` tie breaking.

- [ ] **Step 4: Run GREEN and full tests**

Run:

```bash
uv run pytest tests/analysis/test_roles.py -v
uv run pytest -q
```

Expected: focused and full suite pass without model loading.

- [ ] **Step 5: Commit**

```bash
git add pianofold/analysis tests/analysis/test_roles.py
git commit -m "feat: add melody bass and harmony analysis"
```

### Task 7: Score symbolic note salience

**Files:**
- Create: `pianofold/arrangement/salience.py`, `tests/arrangement/test_salience.py`

**Interfaces:**
- Consumes `Note`, `ScoreIR`, and `RoleAnalysis`.
- Produces `SalienceWeights(melody=0.45, harmony=0.20, duration=0.15, rhythm=0.10, continuity=0.10)`, `note_salience(note, score, roles, weights=SalienceWeights()) -> float`, and `score_salience(score, roles) -> dict[str, float]`.

- [ ] **Step 1: Write the failing salience tests**

Build a score with a melody anchor and a same-onset duplicated harmony note. Assert the defaults sum to one, the salience result is clamped to `[0, 1]`, repeated calls return identical maps, and the melody anchor has strictly higher salience than redundant harmony.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/arrangement/test_salience.py -v`

Expected: FAIL because `pianofold.arrangement.salience` is absent.

- [ ] **Step 3: Implement one centralized weighted formula**

Compute duration importance by dividing the note duration by the score's longest duration, rhythmic importance from onset-slice cardinality (first/outer anchor notes receive the highest value), and continuity from immediately adjacent same-instrument notes with a pitch gap at most five semitones. Combine exactly the five named fields using `SalienceWeights`; clamp and round only at comparison/output boundaries, not inside the calculation.

- [ ] **Step 4: Run GREEN and full tests**

Run:

```bash
uv run pytest tests/arrangement/test_salience.py -v
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pianofold/arrangement/salience.py tests/arrangement/test_salience.py
git commit -m "feat: add symbolic note salience scoring"
```

### Task 8: Define difficulty profiles

**Files:**
- Create: `pianofold/arrangement/profiles.py`, `tests/arrangement/test_profiles.py`

**Interfaces:**
- Produces frozen `DifficultyProfile(name, max_rh_polyphony, max_lh_polyphony, max_rh_span, max_lh_span, leap_weight, span_weight, density_weight, fidelity_weight)`.
- Produces constants `SIMPLE`, `STANDARD`, `RICH`, and `profile_for(name: str) -> DifficultyProfile`.

- [ ] **Step 1: Write failing profile tests**

Assert names are lowercase `simple`, `standard`, and `rich`; Simple has lower right-hand polyphony and a higher density penalty than Rich; Standard falls between them; `profile_for` is case-insensitive and raises `ValueError` for an unknown name.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/arrangement/test_profiles.py -v`

Expected: FAIL because no profile module exists.

- [ ] **Step 3: Implement three explicit heuristic presets**

Set Simple to RH/LH polyphony `2/2`, spans `9/12`, high leap/span/density weights, and lower fidelity weight. Set Standard to `3/3`, `12/12`, balanced weights. Set Rich to `4/4`, `14/14`, lower leap/span/density penalties and higher fidelity weight. Validate all limits and weights are positive at construction.

- [ ] **Step 4: Run GREEN and full tests**

Run:

```bash
uv run pytest tests/arrangement/test_profiles.py -v
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pianofold/arrangement/profiles.py tests/arrangement/test_profiles.py
git commit -m "feat: add difficulty-aware arrangement profiles"
```

### Task 9: Generate bounded voicing candidates

**Files:**
- Create: `pianofold/arrangement/candidates.py`, `tests/arrangement/test_candidates.py`

**Interfaces:**
- Produces frozen `Voicing(left: tuple[int, ...], right: tuple[int, ...], source_note_ids: tuple[str, ...])`.
- Produces `generate_voicing_candidates(notes: Sequence[Note], salience: Mapping[str, float], profile: DifficultyProfile) -> list[Voicing]`.

- [ ] **Step 1: Write failing candidate tests**

Use an onset slice with bass, a melody, central pitches 55–67, doubled tones, and more than eight notes. Assert no more than 32 unique candidates, every candidate obeys hand polyphony/span limits, high-salience outer melody/bass appear where feasible, central pitches appear in at least one valid alternative hand allocation, empty input returns one empty Voicing, and repeated calls return the same ordered list.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/arrangement/test_candidates.py -v`

Expected: FAIL because the candidate module is absent.

- [ ] **Step 3: Implement constrained finite generation**

Sort notes by `(-salience[note.id], note.pitch, note.id)`, retain the top eight, then forcibly include the highest-pitch and lowest-pitch source note if each is absent. Enumerate only each retained note's legal hand options: lower than 55 left, greater than 67 right, and central pitches either hand. Deduplicate by `(left, right, source_note_ids)`, discard hard violations of per-hand polyphony/span and empty source IDs, sort candidates lexicographically, and return at most 32. Preserve source IDs in every candidate.

- [ ] **Step 4: Run GREEN and full tests**

Run:

```bash
uv run pytest tests/arrangement/test_candidates.py -v
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pianofold/arrangement/candidates.py tests/arrangement/test_candidates.py
git commit -m "feat: generate constrained piano voicing candidates"
```

### Task 10: Model playability and symbolic fidelity

**Files:**
- Create: `pianofold/arrangement/playability.py`, `pianofold/evaluation/fidelity.py`, `tests/arrangement/test_playability.py`, `tests/arrangement/test_fidelity.py`

**Interfaces:**
- Consumes `Voicing` and `DifficultyProfile`.
- Produces `voicing_cost(previous: Voicing | None, current: Voicing, profile: DifficultyProfile) -> float` and `fidelity_score(source_notes: Sequence[Note], voicing: Voicing, salience: Mapping[str, float]) -> float`.

- [ ] **Step 1: Write failing cost and fidelity tests**

Assert a first voicing has no leap cost; larger center movement costs more after seven semitones; profile-near spans cost less than spans over a profile limit; crossing costs more but remains finite; high polyphony costs more. Assert a candidate retaining melody/bass/high-salience notes scores above a sparse low-salience candidate, and pitch-class coverage improves a chord candidate's score.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/arrangement/test_playability.py tests/arrangement/test_fidelity.py -v`

Expected: FAIL because cost and fidelity modules are absent.

- [ ] **Step 3: Implement deterministic component scores**

For each nonempty hand calculate span and center using arithmetic mean. Add soft span excess multiplied by `span_weight`; add per-hand leap excess beyond seven semitones multiplied by `leap_weight`; add total polyphony excess over two per hand multiplied by `density_weight`; add a finite crossing penalty when max(left) is not below min(right); add voice-leading center differences. Fidelity sums retained source-note salience, adds one bonus for retaining the slice's highest and lowest source pitches, adds pitch-class coverage fraction, and subtracts missing salient-note mass. Return finite values only.

- [ ] **Step 4: Run GREEN and full tests**

Run:

```bash
uv run pytest tests/arrangement/test_playability.py tests/arrangement/test_fidelity.py -v
uv run pytest -q
```

Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add pianofold/arrangement/playability.py pianofold/evaluation/fidelity.py tests/arrangement/test_playability.py tests/arrangement/test_fidelity.py
git commit -m "feat: add piano playability and symbolic fidelity scoring"
```

### Task 11: Select arrangements with Beam Search

**Files:**
- Create: `pianofold/arrangement/beam_search.py`, `tests/arrangement/test_beam_search.py`
- Modify: `pianofold/arrangement/__init__.py`

**Interfaces:**
- Consumes `ScoreIR`, `DifficultyProfile`, `analyze_roles`, `score_salience`, candidate generation, cost, and fidelity.
- Produces `arrange(score: ScoreIR, profile: DifficultyProfile, beam_width: int = 16) -> PianoArrangement`.

- [ ] **Step 1: Write failing beam-search tests**

Create a synthetic four-to-eight-bar ScoreIR with melody, bass, chord tones, and movement. Assert output is deterministic, tagged with `profile.name`, keeps each hand inside profile polyphony, and contains no drum source. Compare output profiles: Simple has no more notes and no greater average hand-center leap than Rich; Rich retains at least as many distinct source IDs as Simple; Standard's note/source counts lie within the Simple–Rich range. Assert `beam_width <= 0` raises `ValueError`.

- [ ] **Step 2: Run RED**

Run: `uv run pytest tests/arrangement/test_beam_search.py -v`

Expected: FAIL because `arrange` is absent.

- [ ] **Step 3: Implement compact backpointer search**

Quantize caller-provided ScoreIR only if its onsets are not already on the grid; discard drum notes; group remaining notes by sorted onset. For each slice, generate candidates using full-score salience and profile. Maintain states containing only cumulative score, current Voicing, source time, and a pointer to the prior state. Score each transition as `previous_score + profile.fidelity_weight * fidelity_score(slice_notes, candidate, salience) - voicing_cost(previous_voicing, candidate, profile)`. Sort ties by canonical Voicing and retain the top `beam_width`. Backtrack the best terminal state, convert each selected left/right pitch into PianoNotes using source-note timing and IDs, and sort as the existing exporter expects.

- [ ] **Step 4: Run GREEN, full tests, and real three-profile check**

Run:

```bash
uv run pytest tests/arrangement/test_beam_search.py -v
uv run pytest -q
uv run python -c 'from pathlib import Path; from pianofold.symbolic.serialize import read_score; from pianofold.arrangement.beam_search import arrange; from pianofold.arrangement.profiles import SIMPLE, STANDARD, RICH; from pianofold.export.midi import arrangement_to_midi; score = read_score(Path("data/smoke/score_ir.json")); [arrangement_to_midi(arrange(score, p), Path(f"data/smoke/{p.name}.mid")) for p in (SIMPLE, STANDARD, RICH)]'
```

Inspect note count, retained source IDs, mean per-hand leap, hand spans, and crossings from each real result. Require a visible complexity gradient before declaring Milestone B.

- [ ] **Step 5: Commit and stop**

```bash
git add pianofold/arrangement/beam_search.py pianofold/arrangement/__init__.py tests/arrangement/test_beam_search.py
git commit -m "feat: implement difficulty-aware beam search arranger"
```

Stop after reporting Simple/Standard/Rich note count, density, melody/bass retention, mean left/right leap, max spans, and crossing count. Do not start Task 13+.

## Plan Self-Review

- **Coverage:** Tasks 6–12 map exactly to role analysis, salience, profiles, candidates, playability, fidelity, and Beam Search.
- **Constraints:** The plan preserves the provider boundary, deterministic synthetic testing, profile limits, candidate cap, and no-UI scope.
- **Type consistency:** RoleAnalysis keys all maps by Note ID; salience maps Note ID to float; candidates preserve source IDs; Beam Search returns the pre-existing PianoArrangement.

