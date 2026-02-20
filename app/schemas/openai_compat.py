"""OpenAI-compatible request/response schemas."""

from typing import Any, Literal
from pydantic import BaseModel, Field


# --- Chat Completions ---

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant", "tool"]
    content: str
    name: str | None = None


class ChatCompletionRequest(BaseModel):
    model: str = "gpt-4o"
    messages: list[ChatMessage]
    stream: bool = False
    temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    max_tokens: int | None = None
    top_p: float | None = None
    frequency_penalty: float | None = None
    presence_penalty: float | None = None
    stop: str | list[str] | None = None
    n: int = 1
    user: str | None = None


class ChatCompletionChoice(BaseModel):
    index: int
    message: ChatMessage
    finish_reason: str = "stop"


class UsageInfo(BaseModel):
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


class ChatCompletionResponse(BaseModel):
    id: str
    object: str = "chat.completion"
    created: int
    model: str
    choices: list[ChatCompletionChoice]
    usage: UsageInfo


# --- Image Generation ---

class ImageGenerationRequest(BaseModel):
    prompt: str
    model: str = "dall-e-3"
    n: int = Field(default=1, ge=1, le=10)
    size: str = "1024x1024"
    response_format: Literal["url", "b64_json"] = "url"
    quality: str = "standard"
    style: str | None = None
    user: str | None = None


class ImageData(BaseModel):
    url: str | None = None
    b64_json: str | None = None
    revised_prompt: str | None = None


class ImageGenerationResponse(BaseModel):
    created: int
    data: list[ImageData]


# --- Video Generation (custom, not part of OpenAI standard) ---

class VideoGenerationRequest(BaseModel):
    prompt: str
    model: str = "mock-video-v1"
    duration: int = Field(default=4, ge=1, le=60)
    fps: int = Field(default=8, ge=1, le=60)
    size: str = "512x512"
    n: int = Field(default=1, ge=1, le=4)
    user: str | None = None


class VideoData(BaseModel):
    url: str | None = None
    b64_json: str | None = None


class VideoGenerationResponse(BaseModel):
    created: int
    data: list[VideoData]


# --- Models list ---

class ModelInfo(BaseModel):
    id: str
    object: str = "model"
    created: int
    owned_by: str = "remote-generation-service"


class ModelListResponse(BaseModel):
    object: str = "list"
    data: list[ModelInfo]


# --- Real generation requests (submitted via UI, not OpenAI-compatible) ---

class RealImageRequest(BaseModel):
    prompt: str
    workflow: str = ""  # workflow template filename (without .json)
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    steps: int = 20
    cfg_scale: float = 7.0
    seed: int = -1  # -1 = random
    batch_size: int = 1


class RealVideoRequest(BaseModel):
    prompt: str
    workflow: str = ""
    negative_prompt: str = ""
    width: int = 512
    height: int = 512
    frames: int = 16
    fps: int = 8
    steps: int = 20
    seed: int = -1
