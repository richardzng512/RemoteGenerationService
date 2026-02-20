# RemoteGenerationService

A Python service that acts as a local AI generation backend with two modes:

1. **Mock mode** — Returns simulated responses to OpenAI-compatible API calls. Used by other projects to test without real AI.
2. **Real mode** — Sends jobs to ComfyUI for actual image/video generation.

Includes a web UI for configuration, job monitoring, and output management. Designed to run on a GPU workstation and be accessed from other machines on the local network.

## Quick Start

### Windows

```bat
:: 1. Setup (first time only)
setup_windows.bat

:: 2. Start
start_windows.bat
```

Then open: **http://localhost:8000**

### Manual

```bash
python -m venv .venv
.venv/Scripts/activate      # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python run.py
```

## Features

### Mock API (OpenAI-compatible)
Point other projects at `http://<this-machine>:8000` instead of `https://api.openai.com`:

```python
import openai
client = openai.OpenAI(
    base_url="http://localhost:8000/v1",
    api_key="mock"  # any value works
)
response = client.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello"}]
)
```

**Endpoints:**
- `POST /v1/chat/completions` — LLM chat (streaming supported)
- `POST /v1/images/generations` — Image generation (DALL-E compatible)
- `POST /v1/video/generations` — Video generation (custom)
- `GET  /v1/models` — Lists available mock models

**Configurable behavior:**
- Response delays (min/max) per type
- Error rate simulation (0–100%)
- Custom response templates

### Real Generation (ComfyUI)
Run ComfyUI with `--listen` flag, then:
1. Switch to **Real** mode in the dashboard
2. Upload your ComfyUI workflow JSONs in Settings > Models
3. Submit jobs from Generate > Image or Generate > Video

### Web UI
- **Dashboard** — Service status, job stats, recent jobs
- **Jobs** — Full job list with filtering, live progress, output preview
- **Generate** — Submit LLM/image/video jobs with a form
- **Settings** — Configure all behavior from the browser

### File Transfer
- **HTTP** (default): Generated files served at `/outputs/`. Access from any machine at `http://<service-ip>:8000/outputs/`
- **SMB** (optional): Push files to a Windows share automatically. Configure in Settings > Transfer.

## Configuration

Copy `.env.example` to `.env` and edit as needed. All settings are also editable live from the web UI.

Key settings:

| Setting | Default | Description |
|---|---|---|
| `SERVICE_MODE` | `mock` | `mock` or `real` |
| `COMFYUI_BASE_URL` | `http://localhost:8188` | ComfyUI API URL |
| `TRANSFER_MODE` | `http` | `http` or `smb` |
| `MOCK_LLM_DELAY_MIN/MAX` | `0.5 / 2.0` | Mock LLM response delay (seconds) |
| `MOCK_ERROR_RATE` | `0.0` | Fraction of requests that fail (0.0–1.0) |

## ComfyUI Integration

1. Start ComfyUI with: `python main.py --listen`
2. In the web UI, go to Settings > Models
3. Click **Upload** and upload your workflow `.json` files
4. When generating, select the workflow from the dropdown

The service injects your prompt and parameters (size, steps, seed, etc.) into the workflow automatically by finding the relevant nodes (CLIPTextEncode, KSampler, EmptyLatentImage, etc.).

## API Documentation

Interactive API docs available at: **http://localhost:8000/docs**

## Project Structure

```
app/
├── main.py              # FastAPI app factory
├── config.py            # Settings (Pydantic BaseSettings)
├── database.py          # SQLAlchemy async engine
├── models/              # ORM models (jobs, settings, templates)
├── schemas/             # Pydantic schemas (OpenAI-compat, job status)
├── routers/
│   ├── mock/            # POST /v1/chat/completions, /images/generations, /video/generations
│   ├── real/            # POST /api/real/image, /video, ComfyUI workflow CRUD
│   ├── jobs.py          # Job management + SSE progress
│   ├── files.py         # File download + SMB transfer
│   ├── settings.py      # Settings API + template CRUD
│   └── ui.py            # All HTML pages and HTMX partials
├── services/
│   ├── mock/            # Mock LLM/image/video logic
│   ├── real/            # ComfyUI REST client
│   ├── job_service.py   # Job execution dispatcher
│   └── transfer_service.py  # HTTP/SMB file transfer
├── core/
│   ├── job_queue.py     # asyncio job worker
│   └── events.py        # SSE broadcaster
└── templates/           # Jinja2 HTML templates
```
