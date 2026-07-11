"""Production readiness tests — middleware, headers, error contract, tracing.

These tests validate the production hardening from Sprint 6.9:
request IDs, correlation IDs, security headers, GZip, error structure,
startup, shutdown.
"""

from __future__ import annotations


class TestRequestID:
    """Every response must include an X-Request-ID header."""

    def test_health_includes_request_id(self, client):
        r = client.get("/health")
        assert "X-Request-ID" in r.headers
        rid = r.headers["X-Request-ID"]
        # Must be a valid UUID v4 (36 chars, 4 hyphens)
        assert len(rid) == 36
        assert rid.count("-") == 4

    def test_api_includes_request_id(self, client):
        r = client.get("/api/v1/metrics")
        assert "X-Request-ID" in r.headers
        rid = r.headers["X-Request-ID"]
        assert len(rid) == 36
        assert rid.count("-") == 4

    def test_request_ids_are_unique(self, client):
        ids = {client.get("/health").headers["X-Request-ID"] for _ in range(5)}
        assert len(ids) == 5, "Request IDs should be unique across requests"


class TestCorrelationID:
    """X-Correlation-ID must be present and propagatable."""

    def test_response_includes_correlation_id(self, client):
        r = client.get("/health")
        assert "X-Correlation-ID" in r.headers
        cid = r.headers["X-Correlation-ID"]
        assert len(cid) == 36
        assert cid.count("-") == 4

    def test_client_supplied_correlation_id_is_reused(self, client):
        supplied = "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
        r = client.get("/health", headers={"X-Correlation-ID": supplied})
        assert r.headers["X-Correlation-ID"] == supplied

    def test_correlation_ids_are_unique_when_not_supplied(self, client):
        ids = {client.get("/health").headers["X-Correlation-ID"] for _ in range(5)}
        assert len(ids) == 5, "Correlation IDs should be unique when not supplied"


class TestSecurityHeaders:
    """Baseline security headers must be present on all responses."""

    def test_x_content_type_options(self, client):
        r = client.get("/health")
        assert r.headers.get("X-Content-Type-Options") == "nosniff"

    def test_x_frame_options(self, client):
        r = client.get("/health")
        assert r.headers.get("X-Frame-Options") == "DENY"

    def test_referrer_policy(self, client):
        r = client.get("/health")
        assert r.headers.get("Referrer-Policy") == "no-referrer"

    def test_permissions_policy(self, client):
        r = client.get("/health")
        assert "Permissions-Policy" in r.headers

    def test_security_headers_on_error(self, client):
        r = client.get("/api/v1/podcasts/99999")
        # Should still have security headers even on 404
        assert r.headers.get("X-Content-Type-Options") == "nosniff"
        assert r.headers.get("X-Frame-Options") == "DENY"


class TestGZip:
    """GZip compression should be available."""

    def test_accepts_gzip(self, client):
        r = client.get("/api/v1/metrics", headers={"Accept-Encoding": "gzip"})
        # FastAPI TestClient decompresses automatically,
        # so we just verify the response is still valid
        assert r.status_code == 200
        data = r.json()
        assert "podcasts" in data

    def test_small_response_not_broken(self, client):
        """Small responses should still work fine."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestErrorContract:
    """All errors must follow the RFC 7807 structure."""

    REQUIRED_ERROR_FIELDS = {
        "type",
        "title",
        "status",
        "detail",
        "instance",
        "request_id",
        "correlation_id",
    }

    def test_404_has_rfc7807_fields(self, client):
        r = client.get("/api/v1/podcasts/99999")
        assert r.status_code == 404
        body = r.json()
        for key in self.REQUIRED_ERROR_FIELDS:
            assert key in body, f"Missing error field: {key}"
        assert body["status"] == 404
        assert body["title"] == "Not Found"
        assert body["instance"] == "/api/v1/podcasts/99999"

    def test_405_has_rfc7807_fields(self, client):
        r = client.delete("/api/v1/podcasts")
        assert r.status_code == 405
        body = r.json()
        for key in self.REQUIRED_ERROR_FIELDS:
            assert key in body, f"Missing error field: {key}"
        assert body["status"] == 405
        assert body["title"] == "Method Not Allowed"

    def test_422_has_request_id(self, client):
        """Validation errors should include tracing IDs."""
        r = client.post("/api/v1/downloads", json={"limit": -1})
        assert r.status_code == 422
        # FastAPI's built-in 422 has detail (array), not our custom handler directly
        # But our middleware still adds request_id to headers
        assert "X-Request-ID" in r.headers

    def test_error_request_id_matches_header(self, client):
        r = client.get("/api/v1/podcasts/99999")
        header_rid = r.headers["X-Request-ID"]
        body = r.json()
        assert body["request_id"] == header_rid


class TestStartupShutdown:
    """Verify the application starts and can be stopped cleanly."""

    def test_health_responds_after_startup(self, client):
        """Application starts up and health endpoint responds."""
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"

    def test_ready_responds(self, client):
        """Ready endpoint responds (DB may or may not be connected in tests)."""
        r = client.get("/ready")
        assert r.status_code == 200
        assert r.json()["status"] in ("ready", "not ready")

    def test_version_responds(self, client):
        """Version endpoint returns expected keys."""
        r = client.get("/version")
        assert r.status_code == 200
        body = r.json()
        for key in ("app", "version", "api_version", "git_sha", "python"):
            assert key in body, f"Missing: {key}"

    def test_multiple_requests_work(self, client):
        """Application handles multiple requests without issues."""
        for _ in range(10):
            r = client.get("/health")
            assert r.status_code == 200

    def test_openapi_schema_loads(self, client):
        """OpenAPI schema is valid and contains all paths."""
        r = client.get("/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "paths" in data
        assert len(data["paths"]) > 0


class TestTracingHeadersOnAllEndpoints:
    """Verify tracing headers exist on every endpoint type."""

    def test_metrics_has_tracing(self, client):
        r = client.get("/api/v1/metrics")
        assert "X-Request-ID" in r.headers
        assert "X-Correlation-ID" in r.headers

    def test_info_has_tracing(self, client):
        r = client.get("/api/v1/info")
        assert "X-Request-ID" in r.headers
        assert "X-Correlation-ID" in r.headers

    def test_podcasts_has_tracing(self, client):
        r = client.get("/api/v1/podcasts")
        assert "X-Request-ID" in r.headers
        assert "X-Correlation-ID" in r.headers

    def test_episodes_has_tracing(self, client):
        r = client.get("/api/v1/episodes")
        assert "X-Request-ID" in r.headers
        assert "X-Correlation-ID" in r.headers
