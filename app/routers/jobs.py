"""Job management API: list, detail, cancel, SSE progress."""

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.events import event_generator
from app.database import get_db
from app.models.job import GenerationJob, JobStatus
from app.schemas.job import JobListResponse, JobStatusResponse

router = APIRouter()


def _job_to_schema(job: GenerationJob) -> JobStatusResponse:
    return JobStatusResponse(
        id=job.id,
        job_type=job.job_type.value,
        mode=job.mode.value,
        status=job.status.value,
        progress=job.progress,
        progress_message=job.progress_message,
        created_at=job.created_at,
        started_at=job.started_at,
        completed_at=job.completed_at,
        duration_seconds=job.duration_seconds,
        result_text=job.result_text,
        result_files=job.result_files,
        error_message=job.error_message,
        transfer_status=job.transfer_status,
        transfer_path=job.transfer_path,
        request_payload=job.request_payload,
    )


@router.get("", response_model=JobListResponse)
async def list_jobs(
    db: AsyncSession = Depends(get_db),
    status: str | None = Query(None),
    job_type: str | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
):
    stmt = select(GenerationJob).order_by(GenerationJob.created_at.desc())
    if status:
        stmt = stmt.where(GenerationJob.status == status)
    if job_type:
        stmt = stmt.where(GenerationJob.job_type == job_type)

    count_stmt = select(func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    jobs = (await db.execute(stmt)).scalars().all()

    return JobListResponse(
        jobs=[_job_to_schema(j) for j in jobs],
        total=total,
        page=page,
        page_size=page_size,
    )


@router.get("/stats")
async def job_stats(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenerationJob.status, func.count()).group_by(GenerationJob.status))
    counts = {row[0].value: row[1] for row in result.all()}
    return {
        "pending": counts.get("pending", 0),
        "running": counts.get("running", 0),
        "completed": counts.get("completed", 0),
        "failed": counts.get("failed", 0),
        "cancelled": counts.get("cancelled", 0),
        "total": sum(counts.values()),
    }


@router.get("/{job_id}", response_model=JobStatusResponse)
async def get_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    return _job_to_schema(job)


@router.delete("/{job_id}")
async def cancel_job(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status in (JobStatus.COMPLETED, JobStatus.FAILED, JobStatus.CANCELLED):
        raise HTTPException(
            status_code=400,
            detail=f"Cannot cancel a job with status '{job.status.value}'",
        )

    job.status = JobStatus.CANCELLED
    await db.commit()
    return {"job_id": job_id, "status": "cancelled"}


@router.get("/{job_id}/progress")
async def job_progress_sse(job_id: str, db: AsyncSession = Depends(get_db)):
    """SSE endpoint: streams live progress updates for a job."""
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return StreamingResponse(
        event_generator(job_id),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )
