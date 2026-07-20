from __future__ import annotations

import contextlib
import os
import tempfile
import uuid
from pathlib import Path

import structlog
from fastapi import APIRouter, BackgroundTasks, HTTPException, UploadFile
from pydantic import BaseModel

from agents.orchestrator import run_pipeline
from databricks.delta import update_job_status

router = APIRouter(prefix="/api")
log = structlog.get_logger()

# uploads are transient (deleted after processing). Use a writable temp dir by default so
# this works on the read-only Databricks Apps filesystem; override with the UPLOAD_DIR env var.
_upload_base = os.environ.get("UPLOAD_DIR")
if not _upload_base:
    _upload_base = Path(tempfile.gettempdir()) / "defpredict_uploads"
UPLOAD_DIR = Path(_upload_base)
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB
CHUNK_SIZE = 1024 * 1024  # 1 MB


class UploadResponse(BaseModel):
    job_id: str
    status: str


def pipeline_runner(pdf_path: str, job_id: str) -> None:
    try:
        run_pipeline(pdf_path, job_id)
    except Exception:
        log.exception("pipeline_failed", job_id=job_id)
        with contextlib.suppress(Exception):
            update_job_status(job_id, "error")
    finally:
        try:
            Path(pdf_path).unlink(missing_ok=True)
        except OSError:
            log.warning("upload_cleanup_failed", job_id=job_id, path=pdf_path)


@router.post("/analyze", response_model=UploadResponse)
async def analyze(file: UploadFile, background_tasks: BackgroundTasks) -> UploadResponse:
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted.")

    job_id = uuid.uuid4().hex[:12]
    pdf_path = UPLOAD_DIR / f"{job_id}_{file.filename}"
    
    
    size = 0
    too_big = False
    with pdf_path.open("wb") as out:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk: break
            size += len(chunk)
            if size > MAX_FILE_SIZE:
                too_big = True
                break
            out.write(chunk)
    if too_big:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=413, detail="File exceeds 50 MB limit.")
    if size < 100:
        pdf_path.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="File appears to be empty or corrupt.")

    log.info("upload_accepted", job_id=job_id, filename=file.filename, size_bytes=size)

    background_tasks.add_task(pipeline_runner, str(pdf_path), job_id)

    return UploadResponse(job_id=job_id, status="accepted")
