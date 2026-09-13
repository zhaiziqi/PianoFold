"""Atomic JSON persistence for local project status."""

from dataclasses import asdict
import json
from pathlib import Path

from pianofold.projects.models import ProjectMetadata


def create_project_metadata(project_id: str) -> ProjectMetadata:
    """Create a validated initial upload state before processing starts."""
    return ProjectMetadata(
        project_id=project_id,
        status="uploaded",
        stage="uploaded",
        progress=0.0,
        error=None,
        duration=None,
    )


def read_metadata(project_dir: Path) -> ProjectMetadata:
    """Load and validate the complete persisted state."""
    payload = json.loads((project_dir / "metadata.json").read_text(encoding="utf-8"))
    return ProjectMetadata(**payload)


def write_metadata(project_dir: Path, metadata: ProjectMetadata) -> Path:
    """Replace metadata only after a complete JSON document is written."""
    destination = project_dir / "metadata.json"
    temporary = destination.with_suffix(".json.tmp")
    temporary.write_text(
        json.dumps(asdict(metadata), sort_keys=True, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    temporary.replace(destination)
    return destination
