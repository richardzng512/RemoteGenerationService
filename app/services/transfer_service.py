"""File transfer service: HTTP download info and optional SMB push."""

import logging
import socket
from pathlib import Path

from app.config import settings

logger = logging.getLogger(__name__)


def get_local_ip() -> str:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return "localhost"


class TransferService:
    async def get_http_info(self, local_path: str) -> dict:
        """Return HTTP download URL for a local file."""
        path = Path(local_path)
        # Convert absolute path to a URL-friendly relative path under /outputs/
        try:
            rel = path.relative_to(Path(settings.outputs_dir).resolve())
            url_path = "/outputs/" + str(rel).replace("\\", "/")
        except ValueError:
            # File is not under outputs_dir — serve by job endpoint instead
            url_path = f"/outputs/{path.name}"

        ip = get_local_ip()
        return {
            "mode": "http",
            "url": url_path,
            "full_url": f"http://{ip}:{settings.port}{url_path}",
            "filename": path.name,
            "status": "available",
        }

    async def smb_push(self, local_path: str, job_id: str) -> dict:
        """Push a file to a configured Windows share via SMB."""
        try:
            from smb.SMBConnection import SMBConnection  # type: ignore
        except ImportError:
            raise RuntimeError(
                "pysmb is not installed. Add 'pysmb' to requirements.txt and reinstall."
            )

        if not settings.smb_server:
            raise RuntimeError("SMB server is not configured. Check Settings > Transfer.")

        conn = SMBConnection(
            settings.smb_username,
            settings.smb_password,
            "RemoteGenerationService",
            settings.smb_server,
            use_ntlm_v2=True,
        )
        connected = conn.connect(settings.smb_server, 445)
        if not connected:
            raise RuntimeError(f"Cannot connect to SMB server: {settings.smb_server}")

        path = Path(local_path)
        remote_path = f"{settings.smb_target_path}/{job_id}_{path.name}".replace("\\", "/")

        with open(local_path, "rb") as f:
            conn.storeFile(settings.smb_share, remote_path, f)
        conn.close()

        unc = f"\\\\{settings.smb_server}\\{settings.smb_share}{remote_path.replace('/', chr(92))}"
        logger.info(f"SMB push complete: {unc}")
        return {
            "mode": "smb",
            "unc_path": unc,
            "status": "transferred",
        }

    async def transfer(self, local_path: str, job_id: str) -> dict:
        if settings.transfer_mode == "smb":
            return await self.smb_push(local_path, job_id)
        return await self.get_http_info(local_path)
