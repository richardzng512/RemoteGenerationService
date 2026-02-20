"""Mock image generation service."""

import asyncio
import base64
import random
import time
from pathlib import Path

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.settings import ResponseTemplate
from app.schemas.openai_compat import ImageData, ImageGenerationRequest, ImageGenerationResponse

# Minimal 1x1 red PNG as a placeholder (base64 encoded)
_PLACEHOLDER_PNG_B64 = (
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8/5+hHgAHggJ/PchI6QAAAABJRU5ErkJggg=="
)


def _get_placeholder_b64(width: int, height: int) -> str:
    """Return a base64-encoded placeholder PNG."""
    # Check for a static placeholder image first
    placeholder = Path("static/img/placeholder.png")
    if placeholder.exists():
        with open(placeholder, "rb") as f:
            return base64.b64encode(f.read()).decode()
    return _PLACEHOLDER_PNG_B64


class MockImageService:
    async def generate(
        self, request: ImageGenerationRequest, db: AsyncSession
    ) -> ImageGenerationResponse:
        delay = random.uniform(settings.mock_image_delay_min, settings.mock_image_delay_max)
        await asyncio.sleep(delay)

        if random.random() < settings.mock_error_rate:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "message": "Mock error: simulated image generation failure",
                        "type": "server_error",
                        "code": "mock_error",
                    }
                },
            )

        # Parse width/height from size string (e.g. "1024x1024")
        try:
            w, h = (int(x) for x in request.size.split("x"))
        except Exception:
            w, h = 1024, 1024

        # Check for a custom template (a file path to return)
        result = await db.execute(
            select(ResponseTemplate).where(
                ResponseTemplate.job_type == "image",
                ResponseTemplate.is_active == True,  # noqa: E712
            )
        )
        templates = result.scalars().all()

        images = []
        for _ in range(request.n):
            if templates:
                tmpl = random.choice(templates)
                tmpl_path = Path(tmpl.template_content)
                if tmpl_path.exists():
                    with open(tmpl_path, "rb") as f:
                        b64 = base64.b64encode(f.read()).decode()
                    if request.response_format == "b64_json":
                        images.append(ImageData(b64_json=b64, revised_prompt=request.prompt))
                    else:
                        images.append(
                            ImageData(
                                url=f"/static/img/placeholder.png",
                                revised_prompt=request.prompt,
                            )
                        )
                    continue

            # Fallback: return placeholder
            if request.response_format == "b64_json":
                images.append(
                    ImageData(
                        b64_json=_get_placeholder_b64(w, h),
                        revised_prompt=request.prompt,
                    )
                )
            else:
                images.append(
                    ImageData(
                        url=f"/static/img/placeholder.png",
                        revised_prompt=request.prompt,
                    )
                )

        return ImageGenerationResponse(created=int(time.time()), data=images)
