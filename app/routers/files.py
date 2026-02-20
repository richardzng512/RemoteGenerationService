"""File download and transfer API."""

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.job import GenerationJob, JobStatus
from app.services.transfer_service import TransferService

router = APIRouter()


@router.get("/{job_id}/{filename}")
async def download_file(
    job_id: str,
    filename: str,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if not job.result_files:
        raise HTTPException(status_code=404, detail="Job has no output files")

    # Find the matching file
    matched = None
    for file_path in job.result_files:
        if Path(file_path).name == filename:
            matched = file_path
            break

    if not matched:
        raise HTTPException(status_code=404, detail="File not found")

    if not Path(matched).exists():
        raise HTTPException(status_code=410, detail="File no longer exists on disk")

    return FileResponse(matched, filename=filename)


@router.post("/{job_id}/transfer")
async def trigger_transfer(job_id: str, db: AsyncSession = Depends(get_db)):
    """Manually trigger SMB push (or return HTTP info) for a completed job."""
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job.status != JobStatus.COMPLETED:
        raise HTTPException(status_code=400, detail="Job is not completed")

    if not job.result_files:
        raise HTTPException(status_code=400, detail="Job has no output files")

    svc = TransferService()
    results = []
    for file_path in job.result_files:
        info = await svc.transfer(file_path, job_id)
        results.append(info)

    # Update job transfer status
    job.transfer_status = "transferred"
    if results:
        job.transfer_path = results[0].get("unc_path") or results[0].get("full_url", "")
    await db.commit()

    return {"job_id": job_id, "transfers": results}
