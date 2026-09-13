"""Run the reporting entry point without models or artifact writes."""

from pathlib import Path
import subprocess
import sys
from uuid import uuid4

import pytest

from pianofold.symbolic.models import Note, ScoreIR
from pianofold.symbolic.serialize import write_score


SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "evaluate_project.py"


def run_report(root: Path, project_id: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPT), project_id, "--project-root", str(root)],
        capture_output=True, text=True, cwd=root.parent, timeout=30,
    )


def test_cli_prints_three_profiles_without_writing_artifacts(tmp_path: Path) -> None:
    project_id = str(uuid4())
    project = tmp_path / "projects" / project_id
    project.mkdir(parents=True)
    write_score(project / "score_ir.json", ScoreIR((
        Note("bass", 40, 0.01, 0.49, "bass"),
        Note("melody", 72, 0.01, 0.49, "piano"),
    )))
    before = {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in project.iterdir()}
    result = run_report(project.parent, project_id)
    assert result.returncode == 0, result.stderr
    for profile in ("Simple", "Standard", "Rich"):
        assert profile in result.stdout
    assert "notes_per_second" in result.stdout
    assert "4.000" in result.stdout  # Pipeline's 120 BPM quantization ends at .5 s.
    assert not result.stderr
    assert {path: (path.read_bytes(), path.stat().st_mtime_ns) for path in project.iterdir()} == before


@pytest.mark.parametrize("project_id", ["../outside", "invalid", str(uuid4())])
def test_cli_rejects_invalid_or_unknown_project_with_clear_error(tmp_path: Path, project_id: str) -> None:
    result = run_report(tmp_path, project_id)
    assert result.returncode != 0
    assert "error:" in result.stderr.lower()
    assert "project" in result.stderr.lower()
    assert "Traceback" not in result.stderr


def test_cli_rejects_project_missing_score(tmp_path: Path) -> None:
    project_id = str(uuid4())
    (tmp_path / project_id).mkdir()
    result = run_report(tmp_path, project_id)
    assert result.returncode != 0
    assert "score_ir.json" in result.stderr


def test_cli_reports_invalid_score_without_traceback(tmp_path: Path) -> None:
    project_id = str(uuid4())
    project = tmp_path / project_id
    project.mkdir()
    (project / "score_ir.json").write_text('{"notes": []}', encoding="utf-8")
    result = run_report(tmp_path, project_id)
    assert result.returncode != 0
    assert "score_ir.json" in result.stderr
    assert "Traceback" not in result.stderr
