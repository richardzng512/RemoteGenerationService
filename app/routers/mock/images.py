"""POST /v1/images/generations — OpenAI-compatible mock image endpoint."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import GenerationJob, JobStatus, JobType, ServiceMode
from app.schemas.openai_compat import ImageGenerationRequest
from app.services.mock.image_service import MockImageService

router = APIRouter()


@router.post("/images/generations")
async def image_generations(
    request: ImageGenerationRequest,
    db: AsyncSession = Depends(get_db),
):
    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.IMAGE,
        mode=ServiceMode.MOCK,
        status=JobStatus.RUNNING,
        request_payload=request.model_dump(),
        started_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()

    svc = MockImageService()
    response = await svc.generate(request, db)

    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.progress = 100
    job.result_files = [d.url or d.b64_json or "" for d in response.data]
    await db.commit()

    return response
