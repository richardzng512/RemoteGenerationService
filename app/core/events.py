"""Server-Sent Events broadcaster for live job progress."""

import asyncio
import json
import logging
from collections import defaultdict

logger = logging.getLogger(__name__)

# job_id -> list of asyncio.Queue subscribers
_subscribers: dict[str, list[asyncio.Queue]] = defaultdict(list)


def subscribe(job_id: str) -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue()
    _subscribers[job_id].append(q)
    return q


def unsubscribe(job_id: str, q: asyncio.Queue) -> None:
    try:
        _subscribers[job_id].remove(q)
    except ValueError:
        pass
    if not _subscribers[job_id]:
        del _subscribers[job_id]


async def broadcast(job_id: str, data: dict) -> None:
    """Push an event to all subscribers of a job."""
    if job_id not in _subscribers:
        return
    message = f"data: {json.dumps(data)}\n\n"
    dead: list[asyncio.Queue] = []
    for q in list(_subscribers[job_id]):
        try:
            q.put_nowait(message)
        except asyncio.QueueFull:
            dead.append(q)
    for q in dead:
        unsubscribe(job_id, q)


async def event_generator(job_id: str):
    """Async generator for SSE responses."""
    q = subscribe(job_id)
    try:
        while True:
            try:
                message = await asyncio.wait_for(q.get(), timeout=30.0)
                yield message
                # Stop streaming once job is terminal
                try:
                    data = json.loads(message.removeprefix("data: ").strip())
                    if data.get("status") in ("completed", "failed", "cancelled"):
                        break
                except Exception:
                    pass
            except asyncio.TimeoutError:
                # Send a keepalive comment
                yield ": keepalive\n\n"
    finally:
        unsubscribe(job_id, q)
