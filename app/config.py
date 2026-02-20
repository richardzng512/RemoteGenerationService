from typing import Literal
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # Server
    host: str = "0.0.0.0"
    port: int = 8000
    debug: bool = False

    # Service mode
    service_mode: Literal["mock", "real"] = "mock"

    # Database
    database_url: str = "sqlite+aiosqlite:///./data/app.db"

    # ComfyUI
    comfyui_base_url: str = "http://localhost:8188"

    # File Transfer
    transfer_mode: Literal["http", "smb"] = "http"
    smb_server: str = ""
    smb_share: str = ""
    smb_username: str = ""
    smb_password: str = ""
    smb_target_path: str = "/GeneratedFiles"

    # Output directory
    outputs_dir: str = "./outputs"
    workflows_dir: str = "./workflows"

    # Mock LLM delays (seconds)
    mock_llm_delay_min: float = 0.5
    mock_llm_delay_max: float = 2.0

    # Mock image delays (seconds)
    mock_image_delay_min: float = 1.0
    mock_image_delay_max: float = 5.0

    # Mock video delays (seconds)
    mock_video_delay_min: float = 5.0
    mock_video_delay_max: float = 15.0

    # Fraction of mock requests that simulate an error (0.0–1.0)
    mock_error_rate: float = 0.0


settings = Settings()
