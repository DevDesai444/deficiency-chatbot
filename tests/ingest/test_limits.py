"""Tests for the security limits guard (Plan 02, Task 3 / D-16, ASVS L1).

Self-contained: uses tmp_path + a crafted zip, no real DOCX / conftest doc-dict needed.
"""
from __future__ import annotations

import zipfile

import pytest

from ingest.limits import (
    MAX_FILE_BYTES,
    LimitExceeded,
    check_file_limits,
    docx_zip_guard,
    safe_resolve,
)


def test_check_file_limits_rejects_oversized(tmp_path, monkeypatch):
    f = tmp_path / "big.pdf"
    f.write_bytes(b"x" * 1024)
    # lower the cap rather than write 200MB
    monkeypatch.setattr("ingest.limits.MAX_FILE_BYTES", 512)
    with pytest.raises(LimitExceeded) as ei:
        check_file_limits(f)
    assert "too large" in ei.value.reason


def test_check_file_limits_allows_small(tmp_path):
    f = tmp_path / "ok.pdf"
    f.write_bytes(b"x" * 10)
    check_file_limits(f)  # must not raise
    assert f.stat().st_size < MAX_FILE_BYTES


def test_docx_zip_guard_rejects_high_ratio_bomb(tmp_path):
    # One entry of 300KB zeros compresses to a few hundred bytes -> ratio >> 200x.
    bomb = tmp_path / "bomb.docx"
    with zipfile.ZipFile(bomb, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("word/document.xml", b"\0" * (300 * 1024))
    with pytest.raises(LimitExceeded) as ei:
        docx_zip_guard(bomb)
    assert "bomb" in ei.value.reason


def test_docx_zip_guard_rejects_too_many_entries(tmp_path, monkeypatch):
    z = tmp_path / "many.docx"
    monkeypatch.setattr("ingest.limits.MAX_ZIP_ENTRIES", 3)
    with zipfile.ZipFile(z, "w") as zf:
        for i in range(5):
            zf.writestr(f"e{i}.xml", b"hi")
    with pytest.raises(LimitExceeded) as ei:
        docx_zip_guard(z)
    assert "entries" in ei.value.reason


def test_docx_zip_guard_rejects_zip_slip(tmp_path):
    z = tmp_path / "slip.docx"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("../evil.txt", b"pwn")
    with pytest.raises(LimitExceeded) as ei:
        docx_zip_guard(z)
    assert "zip-slip" in ei.value.reason


def test_docx_zip_guard_allows_normal(tmp_path):
    z = tmp_path / "ok.docx"
    with zipfile.ZipFile(z, "w") as zf:
        zf.writestr("word/document.xml", b"<xml>hello</xml>")
    docx_zip_guard(z)  # must not raise


def test_safe_resolve_allows_inside_root(tmp_path):
    (tmp_path / "sub").mkdir()
    f = tmp_path / "sub" / "spec.pdf"
    f.write_bytes(b"x")
    resolved = safe_resolve(tmp_path, f)
    assert resolved.is_relative_to(tmp_path.resolve())


def test_safe_resolve_rejects_dotdot_escape(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    with pytest.raises(LimitExceeded):
        safe_resolve(root, root / ".." / "outside.pdf")


def test_safe_resolve_rejects_symlink_escape(tmp_path):
    root = tmp_path / "corpus"
    root.mkdir()
    outside = tmp_path / "secret.pdf"
    outside.write_bytes(b"secret")
    link = root / "link.pdf"
    link.symlink_to(outside)  # symlink inside root pointing OUT of root
    with pytest.raises(LimitExceeded):
        safe_resolve(root, link)
