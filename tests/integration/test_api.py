"""Integration tests for API routes."""
from __future__ import annotations

from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient


@pytest.fixture()
def client():
    from api.main import app
    return TestClient(app)


class TestHealth:
    def test_health_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] in ("ok", "degraded")
        assert "environment" in data
        assert "data_store" in data


class TestUpload:
    def test_rejects_non_pdf(self, client):
        r = client.post(
            "/api/analyze",
            files={"file": ("test.txt", b"hello world", "text/plain")},
        )
        assert r.status_code == 400
        assert "PDF" in r.json()["detail"]

    def test_rejects_empty_file(self, client):
        r = client.post(
            "/api/analyze",
            files={"file": ("test.pdf", b"tiny", "application/pdf")},
        )
        assert r.status_code == 400
        assert "empty" in r.json()["detail"].lower()

    def test_rejects_oversized_file(self, client):
        big = b"x" * (51 * 1024 * 1024)
        r = client.post(
            "/api/analyze",
            files={"file": ("big.pdf", big, "application/pdf")},
        )
        assert r.status_code == 413

    @patch("api.routes.upload.run_pipeline")
    def test_accepts_valid_pdf(self, mock_pipeline, client, tmp_path):
        pdf_bytes = b"%PDF-1.4" + b"\x00" * 200
        r = client.post(
            "/api/analyze",
            files={"file": ("test.pdf", pdf_bytes, "application/pdf")},
        )
        assert r.status_code == 200
        data = r.json()
        assert "job_id" in data
        assert data["status"] == "accepted"


class TestResults:
    @patch("api.routes.results.get_job")
    def test_returns_404_for_missing_job(self, mock_get, client):
        mock_get.return_value = None
        r = client.get("/api/results/nonexistent")
        assert r.status_code == 404

    @patch("api.routes.results.get_job")
    def test_returns_pending_job(self, mock_get, client):
        mock_get.return_value = {"status": "extracting", "recommendations": None}
        r = client.get("/api/results/abc123")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "extracting"
        assert data["recommendations"] is None

    @patch("api.routes.results.get_job")
    def test_returns_complete_job(self, mock_get, client):
        mock_get.return_value = {
            "status": "complete",
            "recommendations": {
                "job_id": "abc123",
                "recommendations": [],
                "flaws_found": False,
                "inner_loop_count": 0,
                "outer_loop_count": 0,
                "analysis_seconds": 12.5,
            },
        }
        r = client.get("/api/results/abc123")
        assert r.status_code == 200
        data = r.json()
        assert data["status"] == "complete"
        assert data["recommendations"]["flaws_found"] is False
