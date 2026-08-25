from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.factory import ai_pipeline, detector
from app.router import router
from app.settings import settings
from app.ws import router as ws_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    if ai_pipeline is not None:
        ai_pipeline.start()
        if settings.AI_FAIL_STARTUP_IF_UNAVAILABLE and not ai_pipeline.ready:
            raise RuntimeError(f"RVM AI startup failed: {ai_pipeline.error}")

    detector.start()
    try:
        yield
    finally:
        detector.stop()
        if ai_pipeline is not None:
            ai_pipeline.stop()


app = FastAPI(
    title="GreenAfrica RVM API",
    version="2.0.0",
    lifespan=lifespan,
)

app.include_router(router)
app.include_router(ws_router)
