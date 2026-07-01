from __future__ import annotations

import uuid

from fastapi import APIRouter, UploadFile
from pydantic import BaseModel

router = APIRouter(prefix="/api")


class UploadResponse(BaseModel):
    job_id: str
    status: str


@router.post("/analyze", response_model=UploadResponse)
async def analyze(file: UploadFile) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    job_id = uuid.uuid4().hex[:12]
    # TODO: Phase 6 — persist file, launch background pipeline
    return UploadResponse(job_id=job_id, status="accepted")
