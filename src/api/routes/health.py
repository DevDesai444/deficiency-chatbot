from __future__ import annotations

import httpx
from fastapi import APIRouter
from pydantic import BaseModel

from config import get_settings

router = APIRouter()


class HealthStatus(BaseModel):
    status: str
    llm: str
    environment: str


def _check_llm() -> str:
    s = get_settings()
    try:
        r = httpx.get(f"{s.llm_base_url}/models", timeout=3.0)
        return "up" if r.status_code == 200 else f"down: HTTP {r.status_code}"
    except Exception as e:
        return f"down: {type(e).__name__}"


@router.get("/health", response_model=HealthStatus)
def health() -> HealthStatus:
    s = get_settings()
    llm_status = _check_llm()
    overall = "ok" if llm_status == "up" else "degraded"
    return HealthStatus(status=overall, llm=llm_status, environment=s.environment)
