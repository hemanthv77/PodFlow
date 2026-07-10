"""Integration tests."""

from podflow.services.pipeline_service import PipelineService

URL = "https://talkpython.fm/episodes/rss"


class TestEndToEnd:
    def test_pipeline_returns_success(self):
        """Fresh pipeline: download 2, verify counts."""
        r = PipelineService().run(URL, download_limit=2)
        assert r.discovered > 500
        assert r.downloaded <= 2
        assert r.success

    def test_rerun_after_first_is_idempotent(self):
        """Re-run: zero new, zero downloads."""
        PipelineService().run(URL, download_limit=1)
        r = PipelineService().run(URL, download_limit=1)
        assert r.inserted == 0
        assert r.downloaded == 0
        assert r.success
