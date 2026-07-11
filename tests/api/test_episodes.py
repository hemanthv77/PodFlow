"""API integration tests for episodes."""


class TestListEpisodes:
    def test_returns_200(self, client):
        r = client.get("/api/v1/episodes")
        assert r.status_code == 200

    def test_pagination_structure(self, client):
        r = client.get("/api/v1/episodes?limit=5")
        body = r.json()
        for key in ("items", "total", "offset", "limit"):
            assert key in body, f"Missing: {key}"

    def test_filter_by_state(self, client):
        r = client.get("/api/v1/episodes?processing_state=DOWNLOADED&limit=5")
        assert r.status_code == 200

    def test_sort_newest_first(self, client):
        r = client.get("/api/v1/episodes?sort_by=-published_at&limit=3")
        assert r.status_code == 200

    def test_invalid_limit_returns_422(self, client):
        r = client.get("/api/v1/episodes?limit=0")
        assert r.status_code == 422


class TestGetEpisode:
    def test_missing_returns_404(self, client):
        r = client.get("/api/v1/episodes/999999")
        assert r.status_code == 404
        assert "detail" in r.json()
