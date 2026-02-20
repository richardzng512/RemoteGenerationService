"""UI routes: all HTML pages and HTMX partials."""

import json as _json
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.job_queue import enqueue_job
from app.database import get_db
from app.models.job import GenerationJob, JobStatus, JobType, ServiceMode
from app.models.settings import ResponseTemplate
from app.services.real.comfyui_service import get_comfyui_service
from app.services.transfer_service import TransferService, get_local_ip

router = APIRouter()
templates = Jinja2Templates(directory="app/templates")
# tojson is a Flask builtin but not Jinja2 — register it manually
templates.env.filters["tojson"] = (
    lambda v, indent=None: _json.dumps(v, indent=indent, ensure_ascii=False)
)


def _base_ctx(request: Request) -> dict:
    ip = get_local_ip()
    return {
        "request": request,
        "mode": settings.service_mode,
        "network_url": f"http://{ip}:{settings.port}",
        "flash": None,
    }


def _flash(ctx: dict, message: str, type_: str = "info") -> dict:
    ctx["flash"] = {"message": message, "type": type_}
    return ctx


# --- Pages ---

@router.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    ctx = _base_ctx(request)
    return templates.TemplateResponse("dashboard.html", ctx)


@router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(
    request: Request,
    status: str = "",
    job_type: str = "",
    page: int = 1,
):
    ctx = _base_ctx(request)
    ctx.update(
        status_filter=status,
        type_filter=job_type,
        page=page,
    )
    return templates.TemplateResponse("jobs/list.html", ctx)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
async def job_detail(request: Request, job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if not job:
        return HTMLResponse("<h2>Job not found</h2>", status_code=404)
    ctx = _base_ctx(request)
    ctx["job"] = job
    return templates.TemplateResponse("jobs/detail.html", ctx)


@router.get("/generate/llm", response_class=HTMLResponse)
async def generate_llm_page(request: Request):
    ctx = _base_ctx(request)
    return templates.TemplateResponse("generate/llm.html", ctx)


@router.get("/generate/image", response_class=HTMLResponse)
async def generate_image_page(request: Request):
    svc = get_comfyui_service()
    ctx = _base_ctx(request)
    ctx["workflows"] = svc.list_workflows()
    return templates.TemplateResponse("generate/image.html", ctx)


@router.get("/generate/video", response_class=HTMLResponse)
async def generate_video_page(request: Request):
    svc = get_comfyui_service()
    ctx = _base_ctx(request)
    ctx["workflows"] = svc.list_workflows()
    return templates.TemplateResponse("generate/video.html", ctx)


@router.get("/settings", response_class=HTMLResponse)
async def settings_general(request: Request):
    ctx = _base_ctx(request)
    ctx.update(tab="general", settings=settings)
    return templates.TemplateResponse("settings/general.html", ctx)


@router.get("/settings/mock", response_class=HTMLResponse)
async def settings_mock(request: Request):
    ctx = _base_ctx(request)
    ctx.update(tab="mock", settings=settings)
    return templates.TemplateResponse("settings/mock.html", ctx)


@router.get("/settings/models", response_class=HTMLResponse)
async def settings_models(request: Request):
    ctx = _base_ctx(request)
    ctx.update(tab="models", settings=settings)
    return templates.TemplateResponse("settings/models.html", ctx)


@router.get("/settings/transfer", response_class=HTMLResponse)
async def settings_transfer(request: Request):
    ctx = _base_ctx(request)
    ctx.update(tab="transfer", settings=settings)
    return templates.TemplateResponse("settings/transfer.html", ctx)


# --- Form Actions ---

@router.post("/generate/llm/submit")
async def submit_llm(
    request: Request,
    db: AsyncSession = Depends(get_db),
    system_prompt: str = Form(default=""),
    user_message: str = Form(...),
    model: str = Form(default="gpt-4o"),
    temperature: float = Form(default=0.7),
    max_tokens: int | None = Form(default=None),
):
    messages = []
    if system_prompt:
        messages.append({"role": "system", "content": system_prompt})
    messages.append({"role": "user", "content": user_message})

    payload = {
        "model": model,
        "messages": messages,
        "temperature": temperature,
        "stream": False,
    }
    if max_tokens:
        payload["max_tokens"] = max_tokens

    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.LLM,
        mode=ServiceMode.MOCK,  # LLM is always mock
        status=JobStatus.PENDING,
        request_payload=payload,
        created_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()
    await enqueue_job(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.post("/generate/image/submit")
async def submit_image(
    request: Request,
    db: AsyncSession = Depends(get_db),
    prompt: str = Form(...),
    negative_prompt: str = Form(default=""),
    workflow: str = Form(default=""),
    width: int = Form(default=512),
    height: int = Form(default=512),
    steps: int = Form(default=20),
    cfg_scale: float = Form(default=7.0),
    seed: int = Form(default=-1),
    batch_size: int = Form(default=1),
):
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "workflow": workflow,
        "width": width,
        "height": height,
        "steps": steps,
        "cfg_scale": cfg_scale,
        "seed": seed,
        "batch_size": batch_size,
    }
    mode = ServiceMode.REAL if settings.service_mode == "real" else ServiceMode.MOCK
    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.IMAGE,
        mode=mode,
        status=JobStatus.PENDING,
        request_payload=payload,
        created_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()
    await enqueue_job(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.post("/generate/video/submit")
async def submit_video(
    request: Request,
    db: AsyncSession = Depends(get_db),
    prompt: str = Form(...),
    negative_prompt: str = Form(default=""),
    workflow: str = Form(default=""),
    width: int = Form(default=512),
    height: int = Form(default=512),
    frames: int = Form(default=16),
    fps: int = Form(default=8),
    steps: int = Form(default=20),
    seed: int = Form(default=-1),
):
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "workflow": workflow,
        "width": width,
        "height": height,
        "frames": frames,
        "fps": fps,
        "steps": steps,
        "seed": seed,
    }
    mode = ServiceMode.REAL if settings.service_mode == "real" else ServiceMode.MOCK
    job = GenerationJob(
        id=str(uuid.uuid4()),
        job_type=JobType.VIDEO,
        mode=mode,
        status=JobStatus.PENDING,
        request_payload=payload,
        created_at=datetime.now(UTC),
    )
    db.add(job)
    await db.commit()
    await enqueue_job(job.id)
    return RedirectResponse(f"/jobs/{job.id}", status_code=303)


@router.post("/settings/mode")
async def set_mode_form(
    request: Request,
    db: AsyncSession = Depends(get_db),
    mode: str = Form(...),
):
    if mode in ("mock", "real"):
        from app.routers.settings import _set_setting
        settings.service_mode = mode  # type: ignore
        await _set_setting(db, "service_mode", mode)
    return RedirectResponse("/", status_code=303)


@router.post("/settings/save")
async def save_settings(request: Request, db: AsyncSession = Depends(get_db)):
    form = await request.form()
    tab = form.get("tab", "general")

    from app.routers.settings import _set_setting

    setting_fields = [
        "service_mode", "comfyui_base_url",
        "transfer_mode", "smb_server", "smb_share", "smb_username",
        "smb_password", "smb_target_path",
        "mock_llm_delay_min", "mock_llm_delay_max",
        "mock_image_delay_min", "mock_image_delay_max",
        "mock_video_delay_min", "mock_video_delay_max",
        "mock_error_rate",
    ]
    float_fields = {
        "mock_llm_delay_min", "mock_llm_delay_max",
        "mock_image_delay_min", "mock_image_delay_max",
        "mock_video_delay_min", "mock_video_delay_max",
        "mock_error_rate",
    }

    for field in setting_fields:
        if field in form:
            raw = form[field]
            value = float(raw) if field in float_fields else raw
            setattr(settings, field, value)
            await _set_setting(db, field, str(raw))

    # Special: update ComfyUI service URL
    if "comfyui_base_url" in form:
        svc = get_comfyui_service()
        svc.base_url = str(form["comfyui_base_url"]).rstrip("/")

    return RedirectResponse(f"/settings/{tab if tab != 'general' else ''}", status_code=303)


@router.post("/jobs/{job_id}/cancel")
async def cancel_job_form(job_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(GenerationJob).where(GenerationJob.id == job_id))
    job = result.scalar_one_or_none()
    if job and job.status in (JobStatus.PENDING, JobStatus.RUNNING):
        job.status = JobStatus.CANCELLED
        await db.commit()
    return RedirectResponse(f"/jobs/{job_id}", status_code=303)


# --- HTMX Partials ---

@router.get("/api/status", response_class=HTMLResponse)
async def status_partial(request: Request):
    svc = get_comfyui_service()
    comfyui_ok = await svc.is_available()
    html = f"""
    <div>
      <span class="{'dot-green' if comfyui_ok else 'dot-red'}"></span>
      ComfyUI ({svc.base_url}) — {'Connected' if comfyui_ok else 'Unavailable'}
    </div>
    """
    return HTMLResponse(html)


@router.get("/api/stats-partial", response_class=HTMLResponse)
async def stats_partial(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GenerationJob.status, func.count()).group_by(GenerationJob.status)
    )
    counts = {row[0].value: row[1] for row in result.all()}
    total = sum(counts.values())

    cards = [
        ("Running", counts.get("running", 0), "running"),
        ("Completed", counts.get("completed", 0), "completed"),
        ("Failed", counts.get("failed", 0), "failed"),
        ("Total", total, ""),
    ]
    html = ""
    for label, count, status in cards:
        html += f'<div class="stat-card stat-{status}"><big>{count}</big><br><small>{label}</small></div>'
    return HTMLResponse(html)


@router.get("/api/jobs-partial", response_class=HTMLResponse)
async def jobs_partial(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(
        select(GenerationJob).order_by(GenerationJob.created_at.desc()).limit(10)
    )
    jobs = result.scalars().all()
    if not jobs:
        return HTMLResponse("<p><em>No jobs yet.</em></p>")

    rows = ""
    for j in jobs:
        duration = f"{j.duration_seconds:.1f}s" if j.duration_seconds is not None else "—"
        rows += f"""
        <tr>
          <td><a href="/jobs/{j.id}"><code>{j.id[:8]}</code></a></td>
          <td>{j.job_type.value.upper()}</td>
          <td>{j.mode.value}</td>
          <td><span class="badge badge-{j.status.value}">{j.status.value}</span></td>
          <td>{duration}</td>
          <td><small>{j.created_at.strftime('%H:%M:%S')}</small></td>
        </tr>"""

    return HTMLResponse(f"""
    <table>
      <thead><tr>
        <th>ID</th><th>Type</th><th>Mode</th><th>Status</th><th>Duration</th><th>Time</th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>""")


@router.get("/api/jobs-table", response_class=HTMLResponse)
async def jobs_table_partial(
    request: Request,
    db: AsyncSession = Depends(get_db),
    status: str = "",
    job_type: str = "",
    page: int = 1,
    page_size: int = 20,
):
    stmt = select(GenerationJob).order_by(GenerationJob.created_at.desc())
    if status:
        stmt = stmt.where(GenerationJob.status == status)
    if job_type:
        stmt = stmt.where(GenerationJob.job_type == job_type)

    count_result = await db.execute(
        select(func.count()).select_from(stmt.subquery())
    )
    total = count_result.scalar_one()

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    jobs = (await db.execute(stmt)).scalars().all()

    if not jobs:
        return HTMLResponse("<p><em>No jobs found.</em></p>")

    rows = ""
    for j in jobs:
        duration = f"{j.duration_seconds:.1f}s" if j.duration_seconds is not None else "—"
        progress_html = ""
        if j.status.value == "running":
            progress_html = f'<progress value="{j.progress}" max="100" style="height:6px;margin:0;"></progress>'
        rows += f"""
        <tr>
          <td><a href="/jobs/{j.id}"><code>{j.id[:8]}</code></a></td>
          <td>{j.job_type.value.upper()}</td>
          <td>{j.mode.value}</td>
          <td>
            <span class="badge badge-{j.status.value}">{j.status.value}</span>
            {progress_html}
          </td>
          <td>{duration}</td>
          <td><small>{j.created_at.strftime('%Y-%m-%d %H:%M:%S')}</small></td>
          <td>
            <a href="/jobs/{j.id}" class="outline" role="button" style="padding: 0.2rem 0.5rem; font-size:0.8rem;">View</a>
          </td>
        </tr>"""

    pagination = f"<small>Showing {len(jobs)} of {total}</small>"
    return HTMLResponse(f"""
    <table>
      <thead><tr>
        <th>ID</th><th>Type</th><th>Mode</th><th>Status</th><th>Duration</th><th>Created</th><th></th>
      </tr></thead>
      <tbody>{rows}</tbody>
    </table>
    {pagination}""")


@router.get("/api/settings/templates-partial", response_class=HTMLResponse)
async def templates_partial(request: Request, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(ResponseTemplate).order_by(ResponseTemplate.id))
    templates_list = result.scalars().all()
    if not templates_list:
        return HTMLResponse("<p><em>No templates. Add one above.</em></p>")

    rows = ""
    for t in templates_list:
        preview = t.template_content[:60] + "..." if len(t.template_content) > 60 else t.template_content
        active = "✅" if t.is_active else "❌"
        rows += f"""
        <tr>
          <td>{t.name}</td>
          <td>{t.job_type}</td>
          <td><code style="font-size:0.8rem;">{preview}</code></td>
          <td>{active}</td>
          <td>
            <button class="outline contrast" style="padding:0.2rem 0.5rem; font-size:0.8rem;"
              hx-delete="/api/settings/templates/{t.id}"
              hx-target="#template-list"
              hx-swap="innerHTML"
              hx-confirm="Delete this template?">Delete</button>
          </td>
        </tr>"""

    return HTMLResponse(f"""
    <table>
      <thead><tr><th>Name</th><th>Type</th><th>Content</th><th>Active</th><th></th></tr></thead>
      <tbody>{rows}</tbody>
    </table>""")


@router.get("/api/real/comfyui/status-partial", response_class=HTMLResponse)
async def comfyui_status_partial(request: Request):
    svc = get_comfyui_service()
    available = await svc.is_available()
    if available:
        return HTMLResponse('<p style="color: var(--pico-color-green-500);">✅ ComfyUI is reachable</p>')
    return HTMLResponse(f'<p style="color: var(--pico-color-red-500);">❌ Cannot connect to {svc.base_url}</p>')


@router.get("/api/real/comfyui/workflows-partial", response_class=HTMLResponse)
async def comfyui_workflows_partial(request: Request):
    svc = get_comfyui_service()
    workflows = svc.list_workflows()
    if not workflows:
        return HTMLResponse("<p><em>No workflows uploaded yet.</em></p>")

    items = ""
    for wf in workflows:
        items += f"""
        <tr>
          <td><code>{wf}</code></td>
          <td>
            <button class="outline contrast" style="padding:0.2rem 0.5rem; font-size:0.8rem;"
              hx-delete="/api/real/comfyui/workflows/{wf}"
              hx-target="#workflow-list"
              hx-swap="innerHTML"
              hx-confirm="Delete workflow '{wf}'?">Delete</button>
          </td>
        </tr>"""

    return HTMLResponse(f"""
    <table>
      <thead><tr><th>Workflow Name</th><th></th></tr></thead>
      <tbody>{items}</tbody>
    </table>""")
