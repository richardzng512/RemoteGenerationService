"""Entry point: start the RemoteGenerationService server."""

import socket

import uvicorn


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


if __name__ == "__main__":
    from app.config import settings
    host = settings.host
    port = settings.port
    local_ip = get_local_ip()

    print("=" * 60)
    print("  RemoteGenerationService")
    print("=" * 60)
    print(f"  Local:   http://localhost:{port}")
    print(f"  Network: http://{local_ip}:{port}")
    print(f"  API Docs: http://localhost:{port}/docs")
    print("=" * 60)

    uvicorn.run(
        "app.main:app",
        host=host,
        port=port,
        reload=False,
        log_level="info",
    )
