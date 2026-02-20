from datetime import datetime
from pydantic import BaseModel


class JobStatusResponse(BaseModel):
    id: str
    job_type: str
    mode: str
    status: str
    progress: int
    progress_message: str | None
    created_at: datetime
    started_at: datetime | None
    completed_at: datetime | None
    duration_seconds: float | None
    result_text: str | None
    result_files: list[str] | None
    error_message: str | None
    transfer_status: str | None
    transfer_path: str | None
    request_payload: dict

    model_config = {"from_attributes": True}


class JobListResponse(BaseModel):
    jobs: list[JobStatusResponse]
    total: int
    page: int
    page_size: int
