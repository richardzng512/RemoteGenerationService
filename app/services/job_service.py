"""Job execution dispatcher: routes jobs to mock or real services."""

import logging
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import broadcast
from app.models.job import GenerationJob, JobStatus, JobType, ServiceMode

logger = logging.getLogger(__name__)


async def _progress(job: GenerationJob, db: AsyncSession, pct: int, msg: str) -> None:
    job.progress = pct
    job.progress_message = msg
    await db.commit()
    await broadcast(
        job.id,
        {"status": "running", "progress": pct, "progress_message": msg},
    )


async def execute_job(job: GenerationJob, db: AsyncSession) -> None:
    """Dispatch a job to the appropriate service based on mode and type."""
    progress = lambda pct, msg: _progress(job, db, pct, msg)  # noqa: E731

    await progress(1, "Starting")

    if job.mode == ServiceMode.MOCK:
        await _execute_mock(job, db, progress)
    else:
        await _execute_real(job, db, progress)


async def _execute_mock(job: GenerationJob, db: AsyncSession, progress) -> None:
    from app.services.mock.chat_service import MockChatService
    from app.services.mock.image_service import MockImageService
    from app.services.mock.video_service import MockVideoService
    from app.schemas.openai_compat import (
        ChatCompletionRequest,
        ImageGenerationRequest,
        VideoGenerationRequest,
    )

    await progress(10, "Processing mock request")

    payload = job.request_payload

    if job.job_type == JobType.LLM:
        req = ChatCompletionRequest.model_validate(payload)
        svc = MockChatService()
        result = await svc.generate_response(req, db)
        job.result_text = result.choices[0].message.content

    elif job.job_type == JobType.IMAGE:
        req = ImageGenerationRequest.model_validate(payload)
        svc = MockImageService()
        result = await svc.generate(req, db)
        job.result_files = [d.url or d.b64_json or "" for d in result.data]

    elif job.job_type == JobType.VIDEO:
        req = VideoGenerationRequest.model_validate(payload)
        svc = MockVideoService()
        result = await svc.generate(req, db)
        job.result_files = [d.url or "" for d in result.data]

    await progress(90, "Finalizing")


async def _execute_real(job: GenerationJob, db: AsyncSession, progress) -> None:
    from app.services.real.comfyui_service import get_comfyui_service

    payload = job.request_payload

    if job.job_type == JobType.LLM:
        # LLM is always mock — this branch should not be reached
        raise RuntimeError("Real LLM mode is not supported. LLM is always mocked.")

    svc = get_comfyui_service()

    # Resolve workflow
    workflow_name = payload.get("workflow", "")
    workflows = svc.list_workflows()

    if not workflow_name and workflows:
        workflow_name = workflows[0]

    if not workflow_name:
        raise RuntimeError(
            "No ComfyUI workflow specified and no workflows are available. "
            "Upload a workflow in Settings > Models."
        )

    try:
        workflow = svc.load_workflow(workflow_name)
    except FileNotFoundError as e:
        raise RuntimeError(str(e))

    await progress(5, f"Loaded workflow: {workflow_name}")

    # Inject generation params
    workflow = svc.inject_params(workflow, payload)
    await progress(10, "Parameters injected")

    async def comfy_progress(pct: int, msg: str) -> None:
        await progress(pct, msg)

    output_files = await svc.submit_workflow(workflow, progress_callback=comfy_progress)

    job.result_files = output_files
    await progress(98, "Outputs saved")
