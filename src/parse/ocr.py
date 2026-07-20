"""OCR for scanned pages, via the RapidOCR model-serving endpoint on Databricks.

PyMuPDF reads a PDF's embedded text; a scanned page has none of its own -- it's just
an image (or an unreliable scanner-OCR layer underneath). For pages that look scanned
we render the page to a PNG and send it to the RapidOCR endpoint (defpredict-rapidocr),
which returns the recognized text regions with their bounding boxes. RapidOCR itself
runs only on Databricks -- the app never installs it, it just calls the API.

The boxes are what make the result usable: parse.layout turns them back into readable
text (with spaces) and structured tables. Without the boxes, table cells collapse into
a flat list and empty cells silently shift the surrounding numbers into wrong columns.

Where the endpoint isn't configured/reachable (e.g. plain local dev with no Databricks
creds), OCR is skipped and the caller falls back to whatever text layer exists.
"""
from __future__ import annotations

import base64
import json

import fitz
import httpx
import structlog

from config import get_settings
from parse.layout import OCRRegion, reconstruct_page
from schemas.documents import ExtractedTable

log = structlog.get_logger()

# A page whose largest image covers more than this fraction of the page is a scan,
# not a digital page that happens to carry a small logo.
_SCANNED_IMAGE_COVERAGE = 0.5

# The OCR API on Databricks, and the render resolution. 200 dpi is enough for
# document text and keeps the request payload small.
_OCR_ENDPOINT = "defpredict-rapidocr"
_RENDER_DPI = 200


def is_scanned_page(page: fitz.Page) -> bool:
    """True when the page is a scanned image rather than real digital text.

    A scan is one big image covering the page; a digital page has small images at
    most. A glyphless font is the tell-tale of an invisible OCR layer over a scan.
    """
    page_area = abs(page.rect)
    if page_area <= 0:
        return False

    for info in page.get_image_info():
        if abs(fitz.Rect(info["bbox"])) / page_area > _SCANNED_IMAGE_COVERAGE:
            return True

    for font in page.get_fonts():  # noqa: SIM110 - explicit loop is clearer than any()
        if "glyphless" in str(font[3]).lower():
            return True

    return False


def ocr_page(page: fitz.Page) -> tuple[str, list[ExtractedTable]] | None:
    """Render the page, OCR it through Databricks, and reconstruct text + tables.

    Returns (text, tables), or None when the endpoint is not configured or the call
    fails -- the caller then falls back to the embedded text.
    """
    s = get_settings()
    if not s.databricks_host or not s.databricks_token:
        return None  # no OCR API available (e.g. local dev without creds) -> skip

    try:
        pix = page.get_pixmap(dpi=_RENDER_DPI)
        image_b64 = base64.b64encode(pix.tobytes("png")).decode("ascii")
        resp = httpx.post(
            f"{s.databricks_host}/serving-endpoints/{_OCR_ENDPOINT}/invocations",
            headers={"Authorization": f"Bearer {s.databricks_token}"},
            json={"dataframe_records": [{"image_b64": image_b64}]},
            timeout=60.0,
        )
        resp.raise_for_status()
        predictions = resp.json().get("predictions", [])
    except Exception as exc:
        log.warning("ocr_endpoint_failed", page=page.number + 1, error=str(exc)[:200])
        return None

    if not predictions:
        return "", []
    return _reconstruct_prediction(predictions[0], page.number + 1)


def _reconstruct_prediction(payload, page_number: int) -> tuple[str, list[ExtractedTable]]:
    """Turn one endpoint prediction into (text, tables).

    The current endpoint returns a JSON list of region records ({text, x0, y0, x1, y1,
    score}). An older endpoint returned a plain newline-joined string; we still accept
    that so the app keeps working before the endpoint is redeployed -- just without the
    layout/table reconstruction that the boxes enable.
    """
    records = None
    if isinstance(payload, list):
        records = payload
    elif isinstance(payload, str):
        stripped = payload.strip()
        if stripped.startswith("["):
            try:
                records = json.loads(stripped)
            except json.JSONDecodeError:
                records = None
        if records is None:
            return payload, []  # old endpoint: flat text, no boxes to reconstruct from
    else:
        return "", []

    regions = _regions_from_records(records)
    if not regions:
        return "", []
    return reconstruct_page(regions, page_number)


def _regions_from_records(records) -> list[OCRRegion]:
    """Parse endpoint region records into OCRRegions, skipping malformed ones."""
    regions: list[OCRRegion] = []
    for rec in records:
        if not isinstance(rec, dict):
            continue
        text = str(rec.get("text", "")).strip()
        if not text:
            continue
        try:
            regions.append(
                OCRRegion(
                    text=text,
                    x0=float(rec["x0"]),
                    y0=float(rec["y0"]),
                    x1=float(rec["x1"]),
                    y1=float(rec["y1"]),
                    score=float(rec.get("score", 1.0)),
                )
            )
        except (KeyError, TypeError, ValueError):
            continue
    return regions
