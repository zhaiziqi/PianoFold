from fastapi import FastAPI

from apps.api.routes.health import router as health_router

app = FastAPI(title="PianoFold")
app.include_router(health_router)
