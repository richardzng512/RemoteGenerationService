import enum
import uuid
from datetime import UTC, datetime

from sqlalchemy import DateTime, Enum as SAEnum, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class JobType(str, enum.Enum):
    LLM = "llm"
    IMAGE = "image"
    VIDEO = "video"


class JobStatus(str, enum.Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ServiceMode(str, enum.Enum):
    MOCK = "mock"
    REAL = "real"


class GenerationJob(Base):
    __tablename__ = "generation_jobs"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    job_type: Mapped[JobType] = mapped_column(SAEnum(JobType))
    mode: Mapped[ServiceMode] = mapped_column(SAEnum(ServiceMode))
    status: Mapped[JobStatus] = mapped_column(
        SAEnum(JobStatus), default=JobStatus.PENDING
    )

    # Original request stored as JSON
    request_payload: Mapped[dict] = mapped_column(JSON)

    # Results
    result_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    result_files: Mapped[list | None] = mapped_column(JSON, nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Timing
    created_at: Mapped[datetime] = mapped_column(
        DateTime, default=lambda: datetime.now(UTC)
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    # Progress 0–100
    progress: Mapped[int] = mapped_column(Integer, default=0)
    progress_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    # File transfer
    transfer_status: Mapped[str | None] = mapped_column(String(20), nullable=True)
    transfer_path: Mapped[str | None] = mapped_column(Text, nullable=True)

    @property
    def duration_seconds(self) -> float | None:
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None
