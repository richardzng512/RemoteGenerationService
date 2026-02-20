"""Settings API: read/write runtime config, manage response templates."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.models.settings import ResponseTemplate, SystemSetting
from app.schemas.settings import SettingsUpdate, TemplateCreate, TemplateResponse
from app.services.real.comfyui_service import get_comfyui_service

router = APIRouter()


async def _get_setting(db: AsyncSession, key: str) -> str | None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    return row.value if row else None


async def _set_setting(db: AsyncSession, key: str, value: str) -> None:
    result = await db.execute(select(SystemSetting).where(SystemSetting.key == key))
    row = result.scalar_one_or_none()
    if row:
        row.value = value
    else:
        db.add(SystemSetting(key=key, value=value))
    await db.commit()


@router.get("")
async def get_settings(db: AsyncSession = Depends(get_db)):
    """Return the current effective settings (env + DB overrides)."""
    return {
        "service_mode": settings.service_mode,
        "comfyui_base_url": settings.comfyui_base_url,
        "transfer_mode": settings.transfer_mode,
        "smb_server": settings.smb_server,
        "smb_share": settings.smb_share,
        "smb_username": settings.smb_username,
        "smb_target_path": settings.smb_target_path,
        "mock_llm_delay_min": settings.mock_llm_delay_min,
        "mock_llm_delay_max": settings.mock_llm_delay_max,
        "mock_image_delay_min": settings.mock_image_delay_min,
        "mock_image_delay_max": settings.mock_image_delay_max,
        "mock_video_delay_min": settings.mock_video_delay_min,
        "mock_video_delay_max": settings.mock_video_delay_max,
        "mock_error_rate": settings.mock_error_rate,
        "host": settings.host,
        "port": settings.port,
    }


@router.put("")
async def update_settings(update: SettingsUpdate, db: AsyncSession = Depends(get_db)):
    """Update runtime settings. Values persist in the database."""
    changed = update.model_dump(exclude_none=True)

    for key, value in changed.items():
        # Update the in-memory settings object
        setattr(settings, key, value)
        # Persist to DB for restarts
        await _set_setting(db, key, str(value))

        # Special case: update ComfyUI service URL dynamically
        if key == "comfyui_base_url":
            svc = get_comfyui_service()
            svc.base_url = value.rstrip("/")

    return {"updated": list(changed.keys())}


@router.put("/mode")
async def set_mode(mode: str, db: AsyncSession = Depends(get_db)):
    if mode not in ("mock", "real"):
        raise HTTPException(status_code=400, detail="Mode must be 'mock' or 'real'")
    settings.service_mode = mode  # type: ignore
    await _set_setting(db, "service_mode", mode)
    return {"service_mode": mode}


@router.get("/validate")
async def validate_connections():
    """Test connectivity to configured external services."""
    results = {}

    # ComfyUI
    svc = get_comfyui_service()
    results["comfyui"] = {
        "url": svc.base_url,
        "available": await svc.is_available(),
    }

    return results


# --- Response Templates ---

@router.get("/templates", response_model=list[TemplateResponse])
async def list_templates(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ResponseTemplate).order_by(ResponseTemplate.id))
    return result.scalars().all()


@router.post("/templates", response_model=TemplateResponse)
async def create_template(payload: TemplateCreate, db: AsyncSession = Depends(get_db)):
    tmpl = ResponseTemplate(**payload.model_dump())
    db.add(tmpl)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.put("/templates/{template_id}", response_model=TemplateResponse)
async def update_template(
    template_id: int, payload: TemplateCreate, db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(ResponseTemplate).where(ResponseTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    for k, v in payload.model_dump().items():
        setattr(tmpl, k, v)
    await db.commit()
    await db.refresh(tmpl)
    return tmpl


@router.delete("/templates/{template_id}")
async def delete_template(template_id: int, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(ResponseTemplate).where(ResponseTemplate.id == template_id)
    )
    tmpl = result.scalar_one_or_none()
    if not tmpl:
        raise HTTPException(status_code=404, detail="Template not found")
    await db.delete(tmpl)
    await db.commit()
    return {"deleted": template_id}
