from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


@router.websocket("/ws/{job_id}")
async def agent_stream(websocket: WebSocket, job_id: str) -> None:
    await websocket.accept()
    try:
        # TODO: Phase 6 — subscribe to EventBus for this job_id, push AgentEvents
        await websocket.send_json({"job_id": job_id, "event_type": "connected"})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
