"""Local project submission, persisted status, and confined artifact downloads."""

from collections.abc import Callable
from dataclasses import replace
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request, UploadFile, status
from fastapi.responses import FileResponse

from pianofold.projects import (
    PianoFoldPipeline,
    ProjectMetadata,
    create_project_metadata,
    read_metadata,
    write_metadata,
)


router = APIRouter(prefix="/api/projects", tags=["projects"])
PROJECT_ROOT = Path("data/projects")
ALLOWED_EXTENSIONS = (".mp3", ".wav", ".m4a", ".flac")
DIFFICULTIES = frozenset({"simple", "standard", "rich"})


def canonical_project_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except ValueError:
        raise HTTPException(status_code=404, detail="Project not found") from None
    if str(parsed) != value:
        raise HTTPException(status_code=404, detail="Project not found")
    return value


def _project_directory(request: Request, project_id: str) -> Path:
    root = Path(request.app.state.project_root).resolve()
    directory = root / canonical_project_id(project_id)
    if directory.resolve() != directory or not directory.is_dir():
        raise HTTPException(status_code=404, detail="Project not found")
    _artifact_path(directory, "metadata.json")
    return directory


def _artifact_path(directory: Path, filename: str) -> Path:
    path = directory / filename
    if path.resolve() != path or not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    return path


def _input_audio_path(directory: Path) -> Path:
    for extension in ALLOWED_EXTENSIONS:
        candidate = directory / f"input{extension}"
        if candidate.is_file():
            return _artifact_path(directory, candidate.name)
    raise HTTPException(status_code=404, detail="Original audio file not found")


def _process_project(factory: Callable[[], PianoFoldPipeline], input_path: Path, project_dir: Path) -> None:
    """Construct the provider only after submission; persist construction failures."""
    try:
        factory().process(input_path, project_dir)
    except Exception as error:
        metadata = read_metadata(project_dir)
        write_metadata(project_dir, replace(
            metadata, status="failed", stage="failed",
            error=str(error).strip() or type(error).__name__,
        ))


@router.post("", status_code=status.HTTP_202_ACCEPTED)
async def create_project(
    background_tasks: BackgroundTasks,
    request: Request,
    audio: UploadFile | str | None = None,
) -> dict[str, str]:
    if audio is None or isinstance(audio, str):
        raise HTTPException(status_code=400, detail="Audio file is required")
    extension = Path(audio.filename or "").suffix.lower()
    if extension not in ALLOWED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported audio extension")
    body = await audio.read()
    if not body:
        raise HTTPException(status_code=400, detail="Audio file is empty")
    project_id = str(uuid4())
    directory = Path(request.app.state.project_root) / project_id
    directory.mkdir(parents=True)
    input_path = directory / f"input{extension}"
    input_path.write_bytes(body)
    write_metadata(directory, create_project_metadata(project_id))
    background_tasks.add_task(_process_project, request.app.state.pipeline_factory, input_path, directory)
    return {"project_id": project_id, "status": "processing"}


@router.get("/{project_id}")
def get_project(project_id: str, request: Request) -> ProjectMetadata:
    return read_metadata(_project_directory(request, project_id))


@router.post("/{project_id}/regenerate", status_code=status.HTTP_202_ACCEPTED)
def regenerate_project(
    project_id: str,
    background_tasks: BackgroundTasks,
    request: Request,
) -> dict[str, str]:
    """Re-run a completed local project without asking the user to upload again."""
    directory = _project_directory(request, project_id)
    metadata = read_metadata(directory)
    if metadata.status == "processing":
        raise HTTPException(status_code=409, detail="This project is already processing")
    input_path = _input_audio_path(directory)
    write_metadata(directory, replace(
        metadata,
        status="processing",
        stage="transcribing",
        progress=0.0,
        error=None,
        duration=None,
        melody_mode=None,
        notice=None,
        generation=metadata.generation + 1,
    ))
    background_tasks.add_task(_process_project, request.app.state.pipeline_factory, input_path, directory)
    return {"project_id": project_id, "status": "processing"}


@router.get("/{project_id}/audio")
def get_audio(project_id: str, request: Request) -> FileResponse:
    directory = _project_directory(request, project_id)
    input_path = _input_audio_path(directory)
    return FileResponse(input_path, filename=input_path.name)


def _arrangement_file(request: Request, project_id: str, difficulty: str, suffix: str) -> FileResponse:
    directory = _project_directory(request, project_id)
    if difficulty not in DIFFICULTIES:
        raise HTTPException(status_code=404, detail="Arrangement not found")
    # Exporters write their files before the atomic done marker is published.
    if read_metadata(directory).status != "done":
        raise HTTPException(status_code=404, detail="Arrangement not ready")
    filename = f"{difficulty}.{suffix}"
    return FileResponse(_artifact_path(directory, filename), filename=filename)


@router.get("/{project_id}/arrangements/{difficulty}/midi")
def get_midi(project_id: str, difficulty: str, request: Request) -> FileResponse:
    return _arrangement_file(request, project_id, difficulty, "mid")


@router.get("/{project_id}/arrangements/{difficulty}/musicxml")
def get_musicxml(project_id: str, difficulty: str, request: Request) -> FileResponse:
    return _arrangement_file(request, project_id, difficulty, "musicxml")
