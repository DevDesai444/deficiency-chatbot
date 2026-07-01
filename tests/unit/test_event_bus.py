"""Unit tests for the event bus."""
from __future__ import annotations

import asyncio

import pytest

from agents.event_bus import emit, subscribe, unsubscribe
from schemas.events import AgentEvent


def _make_event(job_id: str = "test-job", event_type: str = "agent_spawned") -> AgentEvent:
    return AgentEvent(
        job_id=job_id,
        layer="extraction",
        event_type=event_type,
        agent_name="TestAgent",
        message="test",
    )


@pytest.mark.asyncio
async def test_subscribe_and_receive():
    q = subscribe("job-1")
    try:
        event = _make_event("job-1")
        emit(event)
        received = await asyncio.wait_for(q.get(), timeout=1.0)
        assert received.job_id == "job-1"
        assert received.agent_name == "TestAgent"
    finally:
        unsubscribe("job-1", q)


@pytest.mark.asyncio
async def test_unsubscribe_stops_events():
    q = subscribe("job-2")
    unsubscribe("job-2", q)
    emit(_make_event("job-2"))
    assert q.empty()


@pytest.mark.asyncio
async def test_events_isolated_by_job():
    q1 = subscribe("job-a")
    q2 = subscribe("job-b")
    try:
        emit(_make_event("job-a"))
        assert not q1.empty()
        assert q2.empty()
    finally:
        unsubscribe("job-a", q1)
        unsubscribe("job-b", q2)


@pytest.mark.asyncio
async def test_multiple_subscribers():
    q1 = subscribe("job-m")
    q2 = subscribe("job-m")
    try:
        emit(_make_event("job-m"))
        r1 = await asyncio.wait_for(q1.get(), timeout=1.0)
        r2 = await asyncio.wait_for(q2.get(), timeout=1.0)
        assert r1.job_id == r2.job_id
    finally:
        unsubscribe("job-m", q1)
        unsubscribe("job-m", q2)
