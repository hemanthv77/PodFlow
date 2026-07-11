"""API integration tests for pipeline executions."""

import pytest


@pytest.mark.slow
class TestPipelineExecutions:
    def test_valid_request_returns_202(self, client, valid_rss_url):
        r = client.post(
            "/api/v1/pipeline-executions", json={"rss_url": valid_rss_url, "download_limit": 1}
        )
        assert r.status_code == 202

    def test_response_schema(self, client, valid_rss_url):
        r = client.post(
            "/api/v1/pipeline-executions", json={"rss_url": valid_rss_url, "download_limit": 1}
        )
        body = r.json()
        for key in (
            "podcast",
            "discovered",
            "inserted",
            "downloaded",
            "skipped",
            "failed",
            "elapsed",
            "success",
        ):
            assert key in body, f"Missing key: {key}"

    def test_invalid_url_returns_422(self, client, invalid_rss_url):
        r = client.post(
            "/api/v1/pipeline-executions", json={"rss_url": invalid_rss_url, "download_limit": 1}
        )
        assert r.status_code == 422

    def test_empty_url_returns_422(self, client):
        r = client.post("/api/v1/pipeline-executions", json={"rss_url": "", "download_limit": 1})
        assert r.status_code == 422

    def test_download_limit_zero_returns_422(self, client, valid_rss_url):
        r = client.post(
            "/api/v1/pipeline-executions", json={"rss_url": valid_rss_url, "download_limit": 0}
        )
        assert r.status_code == 422
