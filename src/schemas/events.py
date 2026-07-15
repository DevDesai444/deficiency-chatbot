from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

EventType = Literal[
    "agent_spawned",
    "agent_message",
    "consensus_start",
    "consensus_vote",
    "consensus_reached",
    "layer_complete",
    "loop_iteration",
    "parse_repair",
    "evidence_dropped",
    "pipeline_complete",
    "error",
]

LayerName = Literal["extraction", "detection", "correction"]


class AgentEvent(BaseModel):
    """WebSocket payload for real-time agent activity."""
    job_id: str
    layer: LayerName
    event_type: EventType
    agent_name: str = ""
    message: str = ""
    metadata: dict = Field(default_factory=dict)
