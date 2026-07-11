"""API integration tests for podcasts."""


class TestListPodcasts:
    def test_returns_200(self, client):
        r = client.get("/api/v1/podcasts")
        assert r.status_code == 200

    def test_pagination_structure(self, client):
        r = client.get("/api/v1/podcasts")
        body = r.json()
        for key in ("items", "total", "offset", "limit"):
            assert key in body, f"Missing: {key}"
        assert isinstance(body["items"], list)
        assert body["offset"] == 0

    def test_limit_caps_results(self, client):
        r = client.get("/api/v1/podcasts?limit=2")
        assert len(r.json()["items"]) <= 2

    def test_sort_by_title(self, client):
        r = client.get("/api/v1/podcasts?sort_by=title")
        assert r.status_code == 200

    def test_invalid_limit_returns_422(self, client):
        r = client.get("/api/v1/podcasts?limit=0")
        assert r.status_code == 422


class TestGetPodcast:
    def test_missing_returns_404(self, client):
        r = client.get("/api/v1/podcasts/999999")
        assert r.status_code == 404
        assert "detail" in r.json()

    def test_negative_id_returns_404(self, client):
        """Negative IDs are valid ints — route matches, query returns nothing, 404."""
        r = client.get("/api/v1/podcasts/-1")
        assert r.status_code == 404
        body = r.json()
        assert "detail" in body
        assert body["status"] == 404
