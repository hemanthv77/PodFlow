"""API integration tests for ingestions."""


class TestIngestions:
    def test_valid_request_returns_201(self, client, valid_rss_url):
        r = client.post("/api/v1/ingestions", json={"rss_url": valid_rss_url})
        assert r.status_code == 201

    def test_response_schema(self, client, valid_rss_url):
        r = client.post("/api/v1/ingestions", json={"rss_url": valid_rss_url})
        body = r.json()
        for key in (
            "podcast",
            "episodes_found",
            "new_episodes",
            "skipped_episodes",
            "duration_seconds",
            "success",
        ):
            assert key in body, f"Missing: {key}"

    def test_invalid_url_returns_422(self, client, invalid_rss_url):
        r = client.post("/api/v1/ingestions", json={"rss_url": invalid_rss_url})
        assert r.status_code == 422

    def test_empty_url_returns_422(self, client):
        r = client.post("/api/v1/ingestions", json={"rss_url": ""})
        assert r.status_code == 422
