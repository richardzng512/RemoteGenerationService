"""Mock video generation service."""

import asyncio
import random
import time

from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.schemas.openai_compat import VideoData, VideoGenerationRequest, VideoGenerationResponse


class MockVideoService:
    async def generate(
        self, request: VideoGenerationRequest, db: AsyncSession
    ) -> VideoGenerationResponse:
        delay = random.uniform(settings.mock_video_delay_min, settings.mock_video_delay_max)
        await asyncio.sleep(delay)

        if random.random() < settings.mock_error_rate:
            raise HTTPException(
                status_code=500,
                detail={
                    "error": {
                        "message": "Mock error: simulated video generation failure",
                        "type": "server_error",
                        "code": "mock_error",
                    }
                },
            )

        videos = []
        for _ in range(request.n):
            videos.append(
                VideoData(
                    url="/static/img/placeholder.png",  # placeholder until real video support
                )
            )

        return VideoGenerationResponse(created=int(time.time()), data=videos)
