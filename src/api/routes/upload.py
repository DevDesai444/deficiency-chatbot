from __future__ import annotations

import contextlib
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from pydantic import BaseModel

from agents.orchestrator import run_pipeline
from databricks.delta import update_job_status

router = APIRouter(prefix="/api")
log = structlog.get_logger()

UPLOAD_DIR = Path("data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB


class UploadResponse(BaseModel):
    job_id: str
    status: str


def _run_pipeline_background(pdf_path: str, job_id: str) -> None:
    try:
        run_pipeline(pdf_path, job_id)
    except Exception:
        log.exception("pipeline_failed", job_id=job_id)
        with contextlib.suppress(Exception):
            update_job_status(job_id, "error")


@router.post("/analyze", response_model=UploadResponse)
async def analyze(file: UploadFile, background_tasks: BackgroundTasks) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    content = await file.read()
    if len(content) > MAX_FILE_SIZE:
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")
    if len(content) < 100:
        raise HTTPException(status_code=400, detail="File appears to be empty or corrupt.")

    job_id = uuid.uuid4().hex[:12]
    pdf_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    pdf_path.write_bytes(content)

    log.info("upload_accepted", job_id=job_id, filename=file.filename, size_bytes=len(content))

    background_tasks.add_task(_run_pipeline_background, str(pdf_path), job_id)

    return UploadResponse(job_id=job_id, status="accepted")
