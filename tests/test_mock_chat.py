"""Tests for the mock chat completions endpoint."""

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_chat_completions_basic(client: AsyncClient):
    response = await client.post(
        "/v1/chat/completions",
        json={
            "model": "gpt-4o",
            "messages": [{"role": "user", "content": "Hello"}],
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "chat.completion"
    assert len(data["choices"]) == 1
    assert data["choices"][0]["message"]["role"] == "assistant"
    assert data["choices"][0]["message"]["content"]


@pytest.mark.asyncio
async def test_chat_completions_models_list(client: AsyncClient):
    response = await client.get("/v1/models")
    assert response.status_code == 200
    data = response.json()
    assert data["object"] == "list"
    assert len(data["data"]) > 0


@pytest.mark.asyncio
async def test_image_generations(client: AsyncClient):
    response = await client.post(
        "/v1/images/generations",
        json={
            "prompt": "A test image",
            "n": 1,
            "size": "512x512",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data
    assert len(data["data"]) == 1


@pytest.mark.asyncio
async def test_video_generations(client: AsyncClient):
    response = await client.post(
        "/v1/video/generations",
        json={
            "prompt": "A test video",
            "duration": 4,
            "fps": 8,
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "data" in data


@pytest.mark.asyncio
async def test_jobs_list(client: AsyncClient):
    response = await client.get("/api/jobs")
    assert response.status_code == 200
    data = response.json()
    assert "jobs" in data
    assert "total" in data
