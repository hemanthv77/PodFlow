"""API integration tests for platform endpoints."""


class TestHealth:
    def test_returns_200(self, client):
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


class TestReady:
    def test_returns_200(self, client):
        r = client.get("/ready")
        assert r.status_code == 200
        assert r.json()["status"] in ("ready", "not ready")


class TestVersion:
    def test_returns_200(self, client):
        r = client.get("/version")
        assert r.status_code == 200
        for key in ("app", "version", "git_sha", "python"):
            assert key in r.json(), f"Missing: {key}"


class TestInfo:
    def test_returns_200(self, client):
        r = client.get("/api/v1/info")
        assert r.status_code == 200
        for key in (
            "application",
            "version",
            "python_version",
            "platform",
            "database_backend",
            "api_version",
        ):
            assert key in r.json(), f"Missing: {key}"


class TestMetrics:
    def test_returns_200(self, client):
        r = client.get("/api/v1/metrics")
        assert r.status_code == 200
        for key in (
            "podcasts",
            "episodes",
            "downloaded_episodes",
            "database_backend",
            "uptime_seconds",
        ):
            assert key in r.json(), f"Missing: {key}"

    def test_counts_are_nonnegative(self, client):
        r = client.get("/api/v1/metrics")
        body = r.json()
        assert body["podcasts"] >= 0
        assert body["episodes"] >= 0
        assert body["uptime_seconds"] >= 0


class TestOpenAPI:
    def test_openapi_json(self, client):
        r = client.get("/openapi.json")
        assert r.status_code == 200
        data = r.json()
        assert "paths" in data
        assert "components" in data
        assert len(data["paths"]) >= 8

    def test_tags_exist(self, client):
        r = client.get("/openapi.json")
        data = r.json()
        tag_names = {t["name"] for t in data.get("tags", [])}
        assert "Pipeline Executions" in tag_names
        assert "Podcasts" in tag_names
        assert "Episodes" in tag_names

    def test_operation_ids_unique(self, client):
        r = client.get("/openapi.json")
        data = r.json()
        ids = []
        for ops in data["paths"].values():
            for op in ops.values():
                ids.append(op.get("operationId"))
        assert len(ids) == len(set(ids)), f"Duplicate operationIds: {ids}"
