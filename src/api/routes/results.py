from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from databricks.delta import get_job

router = APIRouter(prefix="/api")


class JobResult(BaseModel):
    job_id: str
    status: str
    faults: dict[str, Any] | None = None
    error: str | None = None


@router.get("/results/{job_id}", response_model=JobResult)
async def get_results(job_id: str) -> JobResult:
    job = get_job(job_id)
    if job is None:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    # The detection layer's FaultReport is stored in the flaw_report column.
    return JobResult(
        job_id=job_id,
        status=job["status"],
        faults=job.get("flaw_report"),
        error=None,
    )
