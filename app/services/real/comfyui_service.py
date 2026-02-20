"""ComfyUI REST API client for real image and video generation."""

import asyncio
import copy
import json
import logging
import random
import uuid
from pathlib import Path
from typing import Any, Callable, Coroutine

import httpx

from app.config import settings

logger = logging.getLogger(__name__)


class ComfyUIService:
    def __init__(self):
        self.base_url = settings.comfyui_base_url.rstrip("/")
        self._client = httpx.AsyncClient(timeout=300.0)

    async def is_available(self) -> bool:
        try:
            response = await self._client.get(f"{self.base_url}/system_stats", timeout=5.0)
            return response.status_code == 200
        except Exception:
            return False

    def list_workflows(self) -> list[str]:
        """Return names of workflow JSON files in the workflows directory."""
        wf_dir = Path(settings.workflows_dir)
        if not wf_dir.exists():
            return []
        return sorted(p.stem for p in wf_dir.glob("*.json"))

    def load_workflow(self, name: str) -> dict:
        """Load a workflow JSON by name (without extension)."""
        wf_path = Path(settings.workflows_dir) / f"{name}.json"
        if not wf_path.exists():
            raise FileNotFoundError(f"Workflow '{name}' not found")
        with open(wf_path) as f:
            return json.load(f)

    def save_workflow(self, name: str, content: dict) -> None:
        wf_dir = Path(settings.workflows_dir)
        wf_dir.mkdir(parents=True, exist_ok=True)
        with open(wf_dir / f"{name}.json", "w") as f:
            json.dump(content, f, indent=2)

    def delete_workflow(self, name: str) -> bool:
        wf_path = Path(settings.workflows_dir) / f"{name}.json"
        if wf_path.exists():
            wf_path.unlink()
            return True
        return False

    def inject_params(self, workflow: dict, params: dict) -> dict:
        """
        Inject generation parameters into a workflow by searching for known
        node types and fields. Supports the common ComfyUI node structure.

        Recognized params: prompt, negative_prompt, width, height, steps,
                           cfg_scale, seed, frames, fps, batch_size
        """
        workflow = copy.deepcopy(workflow)
        seed = params.get("seed", -1)
        if seed == -1:
            seed = random.randint(0, 2**32 - 1)

        for node_id, node in workflow.items():
            if not isinstance(node, dict):
                continue
            inputs = node.get("inputs", {})
            class_type = node.get("class_type", "")

            # CLIPTextEncode — positive/negative prompt
            if class_type == "CLIPTextEncode":
                if "text" in inputs:
                    # Heuristic: if node title contains "negative", use negative_prompt
                    meta = node.get("_meta", {})
                    title = meta.get("title", "").lower()
                    if "negative" in title or "neg" in title:
                        inputs["text"] = params.get("negative_prompt", inputs["text"])
                    else:
                        inputs["text"] = params.get("prompt", inputs["text"])

            # EmptyLatentImage / EmptySD3LatentImage
            if class_type in ("EmptyLatentImage", "EmptySD3LatentImage", "EmptyHunyuanLatentVideo"):
                if "width" in inputs:
                    inputs["width"] = params.get("width", inputs["width"])
                if "height" in inputs:
                    inputs["height"] = params.get("height", inputs["height"])
                if "batch_size" in inputs:
                    inputs["batch_size"] = params.get("batch_size", inputs["batch_size"])
                if "length" in inputs:
                    inputs["length"] = params.get("frames", inputs["length"])

            # KSampler / KSamplerAdvanced
            if class_type in ("KSampler", "KSamplerAdvanced"):
                if "steps" in inputs:
                    inputs["steps"] = params.get("steps", inputs["steps"])
                if "cfg" in inputs:
                    inputs["cfg"] = params.get("cfg_scale", inputs["cfg"])
                if "seed" in inputs:
                    inputs["seed"] = seed
                if "noise_seed" in inputs:
                    inputs["noise_seed"] = seed

            # ADE_AnimateDiffSamplerSettings / similar video nodes
            if "fps" in inputs:
                inputs["fps"] = params.get("fps", inputs["fps"])

        return workflow

    async def submit_workflow(
        self,
        workflow: dict,
        progress_callback: Callable[[int, str], Coroutine] | None = None,
    ) -> list[str]:
        """
        Submit a workflow to ComfyUI, poll for completion, and download outputs.

        Returns a list of local file paths for the generated files.
        """
        client_id = str(uuid.uuid4())

        # Queue the prompt
        response = await self._client.post(
            f"{self.base_url}/prompt",
            json={"prompt": workflow, "client_id": client_id},
        )
        response.raise_for_status()
        prompt_id = response.json()["prompt_id"]
        logger.info(f"ComfyUI prompt queued: {prompt_id}")

        if progress_callback:
            await progress_callback(5, "Queued in ComfyUI")

        # Poll until done
        output_files: list[str] = []
        poll_interval = 1.0
        max_wait = 600  # 10 minutes
        elapsed = 0.0

        while elapsed < max_wait:
            await asyncio.sleep(poll_interval)
            elapsed += poll_interval

            hist_response = await self._client.get(
                f"{self.base_url}/history/{prompt_id}"
            )
            if hist_response.status_code != 200:
                continue

            history = hist_response.json()
            if prompt_id not in history:
                # Still queued or running
                if progress_callback:
                    pct = min(int((elapsed / 30) * 80), 80)  # rough estimate
                    await progress_callback(pct, f"Generating... ({int(elapsed)}s elapsed)")
                continue

            prompt_history = history[prompt_id]

            # Check for errors
            if "error" in prompt_history:
                raise RuntimeError(f"ComfyUI error: {prompt_history['error']}")

            # Collect output files
            outputs = prompt_history.get("outputs", {})
            for node_id, node_output in outputs.items():
                for file_list_key in ("images", "videos", "gifs"):
                    for file_info in node_output.get(file_list_key, []):
                        filename = file_info["filename"]
                        subfolder = file_info.get("subfolder", "")
                        file_type = file_info.get("type", "output")

                        local_path = await self._download_output(
                            filename, subfolder, file_type
                        )
                        if local_path:
                            output_files.append(local_path)

            if progress_callback:
                await progress_callback(95, "Downloading outputs")

            break

        if not output_files:
            raise RuntimeError(f"ComfyUI job {prompt_id} timed out or produced no output")

        return output_files

    async def _download_output(
        self, filename: str, subfolder: str, file_type: str
    ) -> str | None:
        """Download a generated file from ComfyUI and save it locally."""
        params = {"filename": filename, "subfolder": subfolder, "type": file_type}
        try:
            response = await self._client.get(
                f"{self.base_url}/view", params=params, timeout=120.0
            )
            response.raise_for_status()
        except Exception as e:
            logger.error(f"Failed to download {filename}: {e}")
            return None

        # Determine output subdirectory by extension
        ext = Path(filename).suffix.lower()
        if ext in (".mp4", ".avi", ".mov", ".webm", ".gif"):
            subdir = "videos"
        else:
            subdir = "images"

        output_dir = Path(settings.outputs_dir) / subdir
        output_dir.mkdir(parents=True, exist_ok=True)

        # Use a unique name to avoid collisions
        unique_name = f"{uuid.uuid4().hex[:8]}_{filename}"
        local_path = output_dir / unique_name
        local_path.write_bytes(response.content)

        logger.info(f"Saved ComfyUI output: {local_path}")
        return str(local_path)

    async def aclose(self) -> None:
        await self._client.aclose()


# Module-level singleton
_comfyui_service: ComfyUIService | None = None


def get_comfyui_service() -> ComfyUIService:
    global _comfyui_service
    if _comfyui_service is None:
        _comfyui_service = ComfyUIService()
    return _comfyui_service
