"""POST /v1/chat/completions — OpenAI-compatible mock chat endpoint."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse

from app.database import get_db
from app.models.job import GenerationJob, JobStatus, JobType, ServiceMode
from app.schemas.openai_compat import ChatCompletionRequest
from app.services.mock.chat_service import MockChatService
from sqlalchemy.ext.asyncio import AsyncSession

router = APIRouter()


@router.post("/chat/completions")
async def chat_completions(
    request: ChatCompletionRequest,
    db: AsyncSession = Depends(get_db),
):
    # Record the request as a job
    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.LLM,
        mode=ServiceMode.MOCK,
        status=JobStatus.RUNNING,
        request_payload=request.model_dump(),
        started_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()

    svc = MockChatService()

    if request.stream:
        async def _stream():
            content_parts = []
            async for chunk in svc.stream_response(request, db):
                content_parts.append(chunk)
                yield chunk
            # Update job record
            job.status = JobStatus.COMPLETED
            job.completed_at = datetime.now(UTC)
            job.progress = 100
            await db.commit()

        return StreamingResponse(_stream(), media_type="text/event-stream")

    response = await svc.generate_response(request, db)

    job.status = JobStatus.COMPLETED
    job.completed_at = datetime.now(UTC)
    job.progress = 100
    job.result_text = response.choices[0].message.content
    await db.commit()

    return response
