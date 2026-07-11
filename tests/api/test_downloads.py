"""API integration tests for downloads."""

import pytest


@pytest.mark.slow
class TestDownloads:
    def test_valid_request_returns_202(self, client):
        r = client.post("/api/v1/downloads", json={"limit": 1})
        assert r.status_code == 202

    def test_response_schema(self, client):
        r = client.post("/api/v1/downloads", json={"limit": 1})
        body = r.json()
        for key in (
            "episodes_checked",
            "episodes_downloaded",
            "episodes_skipped",
            "episodes_failed",
            "total_bytes",
            "duration_seconds",
            "success",
        ):
            assert key in body, f"Missing: {key}"

    def test_limit_default_is_null(self, client):
        r = client.post("/api/v1/downloads", json={})
        assert r.status_code == 202

    def test_limit_negative_returns_422(self, client):
        r = client.post("/api/v1/downloads", json={"limit": -1})
        assert r.status_code == 422

    def test_limit_zero_returns_422(self, client):
        r = client.post("/api/v1/downloads", json={"limit": 0})
        assert r.status_code == 422
