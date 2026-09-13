"""Immutable state of a locally processed audio project."""

from dataclasses import dataclass
from math import isfinite
from pathlib import Path
from typing import Literal
from uuid import UUID


ProjectStatus = Literal["uploaded", "processing", "done", "failed"]
ProjectStage = Literal["uploaded", "transcribing", "analyzing", "arranging", "exporting", "done", "failed"]


@dataclass(frozen=True, slots=True)
class ProjectMetadata:
    """Validated state persisted for clients polling a project."""

    project_id: str
    status: ProjectStatus
    stage: ProjectStage
    progress: float
    error: str | None
    duration: float | None
    model: str = "muscriptor-small"
    device: str = "mps"
    profiles: tuple[str, ...] = ("simple", "standard", "rich")

    def __post_init__(self) -> None:
        try:
            canonical_id = str(UUID(self.project_id))
        except (ValueError, TypeError, AttributeError) as error:
            raise ValueError("project_id must be canonical UUID text") from error
        if canonical_id != self.project_id:
            raise ValueError("project_id must be canonical UUID text")
        if not _finite_number(self.progress) or not 0 <= self.progress <= 1:
            raise ValueError("progress must be finite and between 0 and 1")
        stages = {
            "uploaded": ("uploaded",),
            "processing": ("transcribing", "analyzing", "arranging", "exporting"),
            "done": ("done",),
            "failed": ("failed",),
        }
        if self.status not in stages or self.stage not in stages[self.status]:
            raise ValueError("status and stage must describe the same processing state")
        if self.status == "failed":
            if not isinstance(self.error, str) or not self.error.strip():
                raise ValueError("failed metadata requires a non-empty error")
        elif self.error is not None:
            raise ValueError("error is only allowed for failed metadata")
        if self.duration is not None and (
            not _finite_number(self.duration) or self.duration < 0
        ):
            raise ValueError("duration must be finite and nonnegative")
        object.__setattr__(self, "profiles", tuple(self.profiles))


def _finite_number(value: object) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool) and isfinite(value)


@dataclass(frozen=True, slots=True)
class ProjectResult:
    """A completed processing attempt and its durable project location."""

    project_dir: Path
    metadata: ProjectMetadata
