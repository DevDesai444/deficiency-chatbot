"""Security limits -- the guard both parse paths cross BEFORE the heavy parse (D-16 / ASVS L1).

Ingestion consumes UNTRUSTED submission files from arbitrary sources. There is no size/cap/zip
guard anywhere in the existing parse layer (only a single OCR HTTP timeout at parse/ocr.py:88),
so this module is net-new. It owns byte/entry/path/ratio caps; XXE hardening for DOCX XML
(python-docx/lxml) is applied in Plan 04's parser (T-01-05), not here.

A `LimitExceeded` carries the manifest reason string for the D-16 `parse_failed`/`unsupported`
row -- the corpus loop (Plan 09) catches it and records the row rather than crashing the batch.
"""
from __future__ import annotations

import zipfile
from pathlib import Path

# --- caps (named constants with rationale; layout.py:33-61 style) ------------
MAX_FILE_BYTES = 200 * 1024 * 1024   # a single submission file over 200MB is treated as hostile/degraded -> parse_failed
MAX_PAGES = 5000                     # consumed by the parsers; a doc over 5000 pages is capped
MAX_ZIP_ENTRIES = 5000               # DOCX is a zip; an absurd entry count is a decompression bomb
MAX_UNCOMPRESSED_BYTES = 1 * 1024 ** 3   # 1GB total uncompressed -- bomb ceiling
MAX_COMPRESSION_RATIO = 200          # a single entry expanding >200x is a bomb
PARSE_TIMEOUT_S = 120                # wall-clock ceiling the parsers enforce per document


class LimitExceeded(Exception):
    """Raised when an untrusted file trips a size/entry/path/ratio guard.

    `.reason` is the human-readable string recorded on the D-16 manifest row.
    """

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason


def check_file_limits(path) -> None:
    """Raise LimitExceeded if the file exceeds the byte ceiling (call before the heavy parse)."""
    path = Path(path)
    size = path.stat().st_size
    if size > MAX_FILE_BYTES:
        raise LimitExceeded(f"file too large: {size} bytes > {MAX_FILE_BYTES} cap")


def docx_zip_guard(path) -> None:
    """Decompression-bomb + zip-slip guard for a DOCX (a zip), before `docx.Document()`.

    Raises LimitExceeded if the archive has too many entries, too much total uncompressed
    data, any single entry whose expansion ratio exceeds the cap, or any entry whose name
    escapes the archive root (`..` or absolute -- zip-slip, T-01-06).
    """
    path = Path(path)
    with zipfile.ZipFile(path) as zf:
        infos = zf.infolist()
        if len(infos) > MAX_ZIP_ENTRIES:
            raise LimitExceeded(f"zip has {len(infos)} entries > {MAX_ZIP_ENTRIES} cap")
        total = 0
        for zi in infos:
            name = zi.filename
            if name.startswith("/") or ".." in Path(name).parts:
                raise LimitExceeded(f"zip-slip: entry name escapes root: {name!r}")
            total += zi.file_size
            ratio = zi.file_size / max(zi.compress_size, 1)
            if ratio > MAX_COMPRESSION_RATIO:
                raise LimitExceeded(
                    f"decompression bomb: entry {name!r} ratio {ratio:.0f}x > {MAX_COMPRESSION_RATIO}x cap"
                )
        if total > MAX_UNCOMPRESSED_BYTES:
            raise LimitExceeded(
                f"decompression bomb: {total} uncompressed bytes > {MAX_UNCOMPRESSED_BYTES} cap"
            )


def safe_resolve(root, path) -> Path:
    """Resolve `path` and confirm it stays INSIDE `root`; raise LimitExceeded on any escape.

    `Path.resolve()` follows symlinks and normalizes `..`, so a symlink or `..` that points
    out of the corpus root resolves outside root and is rejected (T-01-03). Returns the
    resolved in-root path.
    """
    root_resolved = Path(root).resolve()
    resolved = Path(path).resolve()
    if not resolved.is_relative_to(root_resolved):
        raise LimitExceeded(f"path escapes corpus root: {path!r}")
    return resolved
