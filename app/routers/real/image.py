"""POST /api/real/image — submit a real image generation job via ComfyUI."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.job_queue import enqueue_job
from app.database import get_db
from app.models.job import GenerationJob, JobStatus, JobType, ServiceMode
from app.schemas.openai_compat import RealImageRequest

router = APIRouter()


@router.post("/image")
async def submit_image_job(
    request: RealImageRequest,
    db: AsyncSession = Depends(get_db),
):
    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.IMAGE,
        mode=ServiceMode.REAL,
        status=JobStatus.PENDING,
        request_payload=request.model_dump(),
        created_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()
    await enqueue_job(job.id)
    return JSONResponse({"job_id": job.id, "status": "pending"}, status_code=202)
