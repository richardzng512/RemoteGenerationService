"""ComfyUI management: workflow CRUD + status check."""

import json

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from app.services.real.comfyui_service import get_comfyui_service

router = APIRouter()


class WorkflowUpload(BaseModel):
    name: str
    content: dict


@router.get("/comfyui/status")
async def comfyui_status():
    svc = get_comfyui_service()
    available = await svc.is_available()
    return {"available": available, "url": svc.base_url}


@router.get("/comfyui/workflows")
async def list_workflows():
    svc = get_comfyui_service()
    return {"workflows": svc.list_workflows()}


@router.post("/comfyui/workflows")
async def upload_workflow(payload: WorkflowUpload):
    svc = get_comfyui_service()
    # Sanitize name
    name = payload.name.strip().replace(" ", "_")
    if not name:
        raise HTTPException(status_code=400, detail="Workflow name cannot be empty")
    svc.save_workflow(name, payload.content)
    return {"name": name, "saved": True}


@router.post("/comfyui/workflows/upload")
async def upload_workflow_file(file: UploadFile = File(...)):
    """Upload a workflow JSON file directly."""
    if not file.filename or not file.filename.endswith(".json"):
        raise HTTPException(status_code=400, detail="Only .json files are accepted")

    content = await file.read()
    try:
        workflow_dict = json.loads(content)
    except json.JSONDecodeError as e:
        raise HTTPException(status_code=400, detail=f"Invalid JSON: {e}")

    name = file.filename.removesuffix(".json").replace(" ", "_")
    svc = get_comfyui_service()
    svc.save_workflow(name, workflow_dict)
    return {"name": name, "saved": True}


@router.delete("/comfyui/workflows/{name}")
async def delete_workflow(name: str):
    svc = get_comfyui_service()
    deleted = svc.delete_workflow(name)
    if not deleted:
        raise HTTPException(status_code=404, detail=f"Workflow '{name}' not found")
    return {"name": name, "deleted": True}
