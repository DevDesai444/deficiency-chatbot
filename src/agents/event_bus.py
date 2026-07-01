from __future__ import annotations

import asyncio
import contextlib
import threading
from collections import defaultdict

from schemas.events import AgentEvent

_queues: dict[str, list[asyncio.Queue[AgentEvent]]] = defaultdict(list)
_lock = threading.Lock()


def subscribe(job_id: str) -> asyncio.Queue[AgentEvent]:
    q: asyncio.Queue[AgentEvent] = asyncio.Queue()
    with _lock:
        _queues[job_id].append(q)
    return q


def unsubscribe(job_id: str, q: asyncio.Queue[AgentEvent]) -> None:
    with _lock:
        if job_id in _queues:
            _queues[job_id] = [existing for existing in _queues[job_id] if existing is not q]
            if not _queues[job_id]:
                del _queues[job_id]


def emit(event: AgentEvent) -> None:
    with _lock:
        listeners = list(_queues.get(event.job_id, []))
    for q in listeners:
        with contextlib.suppress(asyncio.QueueFull):
            q.put_nowait(event)


def emit_sync(
    job_id: str,
    layer: str,
    event_type: str,
    agent_name: str = "",
    message: str = "",
) -> None:
    event = AgentEvent(
        job_id=job_id,
        layer=layer,  # type: ignore[arg-type]
        event_type=event_type,  # type: ignore[arg-type]
        agent_name=agent_name,
        message=message,
    )

    # If called from a background thread, schedule via the running loop
    try:
        loop = asyncio.get_running_loop()
        loop.call_soon_threadsafe(emit, event)
    except RuntimeError:
        emit(event)
