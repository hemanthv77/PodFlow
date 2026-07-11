"""Unit tests for MetricsService."""

from unittest.mock import MagicMock

from podflow.services.metrics_service import MetricsService


class TestMetricsService:
    def test_gather_returns_expected_keys(self):
        session = MagicMock()
        session.query.return_value.filter_by.return_value.count.return_value = 42
        session.query.return_value.count.return_value = 100

        cfg_mock = MagicMock()
        cfg_mock.database_path = "/tmp/test.db"
        cfg_mock.download_path = MagicMock()
        cfg_mock.download_path.exists.return_value = False
        cfg_mock.db_backend = "sqlite"

        svc = MetricsService(session)
        result = svc.gather()

        expected_keys = {
            "podcasts",
            "episodes",
            "downloaded_episodes",
            "failed_downloads",
            "database_backend",
            "database_size_mb",
            "downloads_size_mb",
            "uptime_seconds",
        }
        assert expected_keys == set(
            result.keys()
        ), f"Missing keys: {expected_keys - set(result.keys())}"
        assert result["database_backend"] == "sqlite"
        assert result["uptime_seconds"] >= 0
