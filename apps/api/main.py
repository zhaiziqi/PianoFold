from fastapi import FastAPI

from apps.api.routes.health import router as health_router
from apps.api.routes.projects import PROJECT_ROOT, router as projects_router
from pianofold.projects import PianoFoldPipeline


def create_pipeline() -> PianoFoldPipeline:
    """Build the model adapter only inside a submitted background task."""
    from pianofold.transcription.muscriptor import MuScriptorTranscriber

    return PianoFoldPipeline(MuScriptorTranscriber())


app = FastAPI(title="PianoFold")
app.state.project_root = PROJECT_ROOT
app.state.pipeline_factory = create_pipeline
app.include_router(health_router)
app.include_router(projects_router)
