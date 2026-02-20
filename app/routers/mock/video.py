"""POST /v1/video/generations — custom mock video endpoint."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import GenerationJob, JobStatus, JobType, ServiceMode
from app.schemas.openai_compat import VideoGenerationRequest
from app.services.mock.video_service import MockVideoService

router = APIRouter()


@router.post("/video/generations")
async def video_generations(
    request: VideoGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.VIDEO,
        mode=ServiceMode.MOCK,
        status=JobStatus.RUNNING,
        request_payload=request.model_dump(),
        started_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()

    svc = MockVideoService()
    response = await svc.generate(request, db)

    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.progress = 100
    job.result_files = [d.url or "" for d in response.data]
    await db.commit()

    return response
