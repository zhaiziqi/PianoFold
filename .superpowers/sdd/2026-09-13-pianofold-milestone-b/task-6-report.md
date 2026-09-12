# Task 6 report: deterministic role analysis

## Summary

Added deterministic, provider-independent melody, bass, and harmony heuristics.
`analyze_roles` returns a frozen `RoleAnalysis` whose read-only mappings are
keyed by note ID. Melody favors high, sustained, continuous vocal-like notes
and penalizes low pitches; bass favors low, bass-labelled, onset-local lowest
notes; harmony scores non-anchor notes by onset-local pitch-class rarity.
Anchors select one highest melody and bass score per onset, breaking score ties
by source ID.

## RED

Command:

```text
uv run pytest tests/analysis/test_roles.py -v
```

Output:

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.4, pytest-9.1.1, pluggy-1.6.0 -- /Users/zhaiziqi/Piano_project/.worktrees/milestone-b/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/zhaiziqi/Piano_project/.worktrees/milestone-b
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 0 items / 1 error

==================================== ERRORS ====================================
________________ ERROR collecting tests/analysis/test_roles.py _________________
ImportError while importing test module '/Users/zhaiziqi/Piano_project/.worktrees/milestone-b/tests/analysis/test_roles.py'.
Hint: make sure your test modules/packages have valid Python names.
Traceback:
/opt/anaconda3/lib/python3.12/importlib/__init__.py:90: in import_module
    return _bootstrap._gcd_import(name[level:], package, level)
tests/analysis/test_roles.py:7: in <module>
    from pianofold.analysis import analyze_roles
E   ImportError: cannot import name 'analyze_roles' from 'pianofold.analysis' (unknown location)
=========================== short test summary info ============================
ERROR tests/analysis/test_roles.py
!!!!!!!!!!!!!!!!!!!! Interrupted: 1 error during collection !!!!!!!!!!!!!!!!!!!!
=============================== 1 error in 0.09s ===============================
```

## GREEN

Command:

```text
uv run pytest tests/analysis/test_roles.py -v
```

Output:

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.4, pytest-9.1.1, pluggy-1.6.0 -- /Users/zhaiziqi/Piano_project/.worktrees/milestone-b/.venv/bin/python
cachedir: .pytest_cache
rootdir: /Users/zhaiziqi/Piano_project/.worktrees/milestone-b
configfile: pyproject.toml
plugins: asyncio-1.4.0, anyio-4.15.1
asyncio: mode=Mode.STRICT, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collecting ... collected 3 items

tests/analysis/test_roles.py::test_role_analysis_scores_are_bounded_and_favor_outer_musical_roles PASSED [ 33%]
tests/analysis/test_roles.py::test_role_anchors_are_one_per_onset_and_stably_break_score_ties_by_id PASSED [ 66%]
tests/analysis/test_roles.py::test_harmony_rewards_distinct_pitch_classes_and_discounts_doubles PASSED [100%]

============================== 3 passed in 0.02s ===============================
```

## Full suite

Command:

```text
uv run pytest -q
```

Output:

```text
.........................................................                [100%]
=============================== warnings summary ===============================
.venv/lib/python3.12/site-packages/fastapi/testclient.py:1
  /Users/zhaiziqi/Piano_project/.worktrees/milestone-b/.venv/lib/python3.12/site-packages/starlette/testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

.venv/lib/python3.12/site-packages/starlette/testclient.py:53
  /Users/zhaiziqi/Piano_project/.worktrees/milestone-b/.venv/lib/python3.12/site-packages/starlette/testclient.py:53: DeprecationWarning: The anyio.abc.BlockingPortal alias is deprecated, use anyio.from_thread.BlockingPortal instead.
    _PortalFactoryType = Callable[[], AbstractContextManager[anyio.abc.BlockingPortal]]

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
57 passed, 2 warnings in 1.86s
```

## Files

- `pianofold/analysis/models.py`
- `pianofold/analysis/melody.py`
- `pianofold/analysis/bass.py`
- `pianofold/analysis/harmony.py`
- `pianofold/analysis/__init__.py`
- `tests/analysis/test_roles.py`
- `.superpowers/sdd/2026-09-13-pianofold-milestone-b/task-6-report.md`

## Self-review

- All score maps cover every source-note ID, use deterministic `ScoreIR` order,
  and are made immutable with `MappingProxyType`.
- Every public role score is clamped to `[0, 1]`.
- Anchor ties use `note.id`, so equal scores cannot depend on incoming order.
- Harmony intentionally assigns anchor notes `0.0`, leaving pitch-class rarity
  to non-anchor material as required.
- The synthetic tests construct `ScoreIR` directly and never import or invoke
  MuScriptor.
- `git diff --check` produced no output after the full suite.

## Concerns

The name-token heuristics are deliberately simple and English-oriented; they
are deterministic baseline signals rather than a semantic instrument classifier.
The full suite has two pre-existing third-party deprecation warnings from
Starlette/TestClient and AnyIO.
