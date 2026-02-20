from datetime import datetime
from typing import Literal
from pydantic import BaseModel, Field


class SettingsUpdate(BaseModel):
    service_mode: Literal["mock", "real"] | None = None
    comfyui_base_url: str | None = None
    transfer_mode: Literal["http", "smb"] | None = None
    smb_server: str | None = None
    smb_share: str | None = None
    smb_username: str | None = None
    smb_password: str | None = None
    smb_target_path: str | None = None
    mock_llm_delay_min: float | None = None
    mock_llm_delay_max: float | None = None
    mock_image_delay_min: float | None = None
    mock_image_delay_max: float | None = None
    mock_video_delay_min: float | None = None
    mock_video_delay_max: float | None = None
    mock_error_rate: float | None = Field(default=None, ge=0.0, le=1.0)


class TemplateCreate(BaseModel):
    name: str
    job_type: Literal["llm", "image", "video"]
    template_content: str
    is_active: bool = True


class TemplateResponse(BaseModel):
    id: int
    name: str
    job_type: str
    template_content: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
