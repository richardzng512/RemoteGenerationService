"""FastAPI application factory."""

import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from app.core.job_queue import start_worker, stop_worker
from app.database import init_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # --- Startup ---
    logger.info("Initializing database...")
    await init_db()

    # Load persisted settings from DB
    await _load_db_settings()

    logger.info("Starting job queue worker...")
    await start_worker()

    yield

    # --- Shutdown ---
    logger.info("Stopping job queue worker...")
    await stop_worker()

    # Close ComfyUI client
    from app.services.real.comfyui_service import get_comfyui_service
    svc = get_comfyui_service()
    await svc.aclose()


async def _load_db_settings():
    """Apply any settings persisted in the database (overrides .env defaults)."""
    from sqlalchemy import select
    from app.database import AsyncSessionLocal
    from app.models.settings import SystemSetting
    from app.config import settings

    float_fields = {
        "mock_llm_delay_min", "mock_llm_delay_max",
        "mock_image_delay_min", "mock_image_delay_max",
        "mock_video_delay_min", "mock_video_delay_max",
        "mock_error_rate",
    }
    int_fields = {"port"}

    async with AsyncSessionLocal() as db:
        result = await db.execute(select(SystemSetting))
        for row in result.scalars().all():
            if hasattr(settings, row.key):
                try:
                    if row.key in float_fields:
                        setattr(settings, row.key, float(row.value))
                    elif row.key in int_fields:
                        setattr(settings, row.key, int(row.value))
                    else:
                        setattr(settings, row.key, row.value)
                except (ValueError, AttributeError) as e:
                    logger.warning(f"Could not load setting {row.key}: {e}")


def create_app() -> FastAPI:
    from app.routers import mock, real, jobs, files, settings as settings_router, ui

    app = FastAPI(
        title="RemoteGenerationService",
        description=(
            "A local AI generation service with OpenAI-compatible mock API "
            "and ComfyUI integration for real image/video generation."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )

    # Static files
    import os
    os.makedirs("outputs", exist_ok=True)
    os.makedirs("static/img", exist_ok=True)
    app.mount("/static", StaticFiles(directory="static"), name="static")
    app.mount("/outputs", StaticFiles(directory="outputs"), name="outputs")

    # Mock API (OpenAI-compatible)
    from app.routers.mock import chat, images, video as mock_video
    from fastapi import APIRouter

    mock_router = APIRouter()
    mock_router.include_router(chat.router)
    mock_router.include_router(images.router)
    mock_router.include_router(mock_video.router)

    # GET /v1/models
    import time
    from app.schemas.openai_compat import ModelInfo, ModelListResponse

    @mock_router.get("/models")
    async def list_models():
        mock_models = [
            ModelInfo(id="gpt-4o", created=int(time.time())),
            ModelInfo(id="gpt-4o-mini", created=int(time.time())),
            ModelInfo(id="gpt-3.5-turbo", created=int(time.time())),
            ModelInfo(id="dall-e-3", created=int(time.time())),
            ModelInfo(id="dall-e-2", created=int(time.time())),
            ModelInfo(id="mock-video-v1", created=int(time.time())),
        ]
        return ModelListResponse(data=mock_models)

    app.include_router(mock_router, prefix="/v1", tags=["Mock API (OpenAI-compatible)"])

    # Real generation API
    from app.routers.real import image as real_image, video as real_video, comfyui as comfyui_router

    real_router = APIRouter()
    real_router.include_router(real_image.router)
    real_router.include_router(real_video.router)
    real_router.include_router(comfyui_router.router)

    app.include_router(real_router, prefix="/api/real", tags=["Real Generation"])

    # Job management
    from app.routers import jobs
    app.include_router(jobs.router, prefix="/api/jobs", tags=["Jobs"])

    # File API
    from app.routers import files
    app.include_router(files.router, prefix="/api/files", tags=["Files"])

    # Settings API
    from app.routers import settings as settings_router
    app.include_router(settings_router.router, prefix="/api/settings", tags=["Settings"])

    # UI (last — catches remaining routes)
    from app.routers import ui
    app.include_router(ui.router, tags=["UI"])

    return app


app = create_app()
