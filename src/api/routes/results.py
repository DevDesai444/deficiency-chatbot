from __future__ import annotations

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter(prefix="/api")


class JobResult(BaseModel):
    job_id: str
    status: str
    error: str | None = None


@router.get("/results/{job_id}", response_model=JobResult)
async def get_results(job_id: str) -> JobResult:
    # TODO: Phase 6 — look up job status from store, return recommendations if complete
    raise HTTPException(status_code=404, detail=f"Job {job_id} not found")
