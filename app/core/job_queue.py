"""asyncio-based job queue worker."""

import asyncio
import logging
from datetime import UTC, datetime

from sqlalchemy import select

from app.database import AsyncSessionLocal
from app.models.job import GenerationJob, JobStatus

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_job_queue: asyncio.Queue[str] = asyncio.Queue()


async def enqueue_job(job_id: str) -> None:
    await _job_queue.put(job_id)


async def _worker_loop() -> None:
    while True:
        try:
            job_id = await _job_queue.get()
            logger.info(f"Processing job {job_id}")

            async with AsyncSessionLocal() as db:
                result = await db.execute(
                    select(GenerationJob).where(GenerationJob.id == job_id)
                )
                job = result.scalar_one_or_none()

                if job is None:
                    logger.warning(f"Job {job_id} not found in database")
                    _job_queue.task_done()
                    continue

                if job.status != JobStatus.PENDING:
                    logger.warning(f"Job {job_id} is not pending (status={job.status})")
                    _job_queue.task_done()
                    continue

                job.status = JobStatus.RUNNING
                job.started_at = datetime.now(UTC)
                await db.commit()
                await db.refresh(job)

                try:
                    # Import here to avoid circular imports
                    from app.services.job_service import execute_job

                    await execute_job(job, db)
                    job.status = JobStatus.COMPLETED
                    job.completed_at = datetime.now(UTC)
                    job.progress = 100
                except asyncio.CancelledError:
                    job.status = JobStatus.CANCELLED
                    job.completed_at = datetime.now(UTC)
                    raise
                except Exception as e:
                    logger.exception(f"Job {job_id} failed: {e}")
                    job.status = JobStatus.FAILED
                    job.error_message = str(e)
                    job.completed_at = datetime.now(UTC)

                await db.commit()

                # Broadcast final status
                from app.core.events import broadcast

                await broadcast(
                    job_id,
                    {
                        "status": job.status.value,
                        "progress": job.progress,
                        "progress_message": job.progress_message,
                        "error_message": job.error_message,
                    },
                )

            _job_queue.task_done()

        except asyncio.CancelledError:
            logger.info("Worker loop cancelled")
            break
        except Exception as e:
            logger.exception(f"Unhandled worker error: {e}")


async def start_worker() -> None:
    global _worker_task
    _worker_task = asyncio.create_task(_worker_loop())
    logger.info("Job queue worker started")


async def stop_worker() -> None:
    global _worker_task
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except asyncio.CancelledError:
            pass
        logger.info("Job queue worker stopped")
