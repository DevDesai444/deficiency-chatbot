from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "pipeline_start",
    "layer_start",
    "agent_spawned",
    "agent_message",
    "selection",
    "oracle_complete",
    "layer_complete",
    "pipeline_complete",
    "error",
    "agent_turn",
    "tool_call",
    "budget_update",
    "continuation",
]

LayerName = Literal["parse", "detection", "review"]


class AgentEvent(BaseModel):
    """WebSocket payload for real-time agent activity."""
    job_id: str
    layer: LayerName
    event_type: EventType
    agent_name: str = ""
    message: str = ""
    metadata: dict = Field(default_factory=dict)
