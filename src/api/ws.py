from __future__ import annotations

import asyncio

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from agents.event_bus import subscribe, unsubscribe

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def agent_stream(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    queue = subscribe(job_id)

    try:
        await websocket.send_json({"job_id": job_id, "event_type": "connected"})

        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30.0)
                await websocket.send_json(event.model_dump())

                if event.event_type == "pipeline_complete":
                    break
            except TimeoutError:
                await websocket.send_json({"ping": True})
    except WebSocketDisconnect:
        pass
    finally:
        unsubscribe(job_id, queue)
