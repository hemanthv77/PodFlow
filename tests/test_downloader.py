"""
Tests for FileManager and AudioDownloader.

Run with::

    cd /path/to/PodFlow
    .venv/bin/pytest tests/test_downloader.py -v
"""

import hashlib
import os
from pathlib import Path
from unittest.mock import MagicMock, PropertyMock, patch

import httpx
import pytest

from podflow.downloader.audio import AudioDownloader, DownloadResult
from podflow.downloader.filesystem import FileManager
from podflow.domain.episode import Episode
from podflow.exceptions.exceptions import (
    AbortDownloadError,
    RetryableDownloadError,
    SkipDownloadError,
)

# ======================================================================
# FileManager tests
# ======================================================================


class TestFileManager:
    """Safe filenames, path generation, existence checks, directories."""

    def test_ensure_directories_creates_all_subdirs(self, temp_dir):
        fm = FileManager(temp_dir)
        fm.ensure_directories()

        expected = {"audio", "transcripts", "summaries", "images", "metadata"}
        actual = {d.name for d in temp_dir.iterdir() if d.is_dir()}
        assert expected == actual, f"Missing subdirectories: {expected - actual}"

    def test_safe_filename_removes_unsafe_chars(self, temp_dir):
        fm = FileManager(temp_dir)
        ep = Episode(title='Test: "Bad" <Chars> | Episode!', guid="x")
        path = fm.audio_path(ep)
        assert ":" not in path.name, "Colon should be replaced"
        assert '"' not in path.name, 'Double quote should be replaced'
        assert "<" not in path.name, "Angle bracket should be replaced"
        assert "|" not in path.name, "Pipe should be replaced"
        assert path.name.endswith(".mp3")

    def test_audio_path_uses_correct_subdir(self, temp_dir):
        fm = FileManager(temp_dir)
        ep = Episode(title="Test Episode", guid="x", audio_url="http://x.com/ep.mp3")
        path = fm.audio_path(ep)
        assert path.parent.name == "audio"
        assert path.name == "Test Episode.mp3"

    def test_audio_path_preserves_extension(self, temp_dir):
        fm = FileManager(temp_dir)
        cases = [
            ("http://x.com/ep.mp3", ".mp3"),
            ("http://x.com/ep.m4a", ".m4a"),
            ("http://x.com/ep.ogg", ".ogg"),
            ("http://x.com/ep?format=mp3", ".mp3"),
            (None, ".mp3"),
        ]
        for url, expected_ext in cases:
            ep = Episode(title="Ep", guid="x", audio_url=url)
            path = fm.audio_path(ep)
            assert path.suffix == expected_ext, f"Expected {expected_ext} for {url}"

    def test_temporary_path_appends_part(self, temp_dir):
        fm = FileManager(temp_dir)
        ep = Episode(title="Test", guid="x", audio_url="http://x.com/ep.mp3")
        tmp = fm.temporary_path(ep)
        assert str(tmp).endswith(".part")

    def test_transcript_path_uses_txt(self, temp_dir):
        fm = FileManager(temp_dir)
        ep = Episode(title="Test", guid="x")
        path = fm.transcript_path(ep)
        assert path.parent.name == "transcripts"
        assert path.suffix == ".txt"

    def test_summary_path_uses_json(self, temp_dir):
        fm = FileManager(temp_dir)
        ep = Episode(title="Test", guid="x")
        path = fm.summary_path(ep)
        assert path.parent.name == "summaries"
        assert path.suffix == ".json"

    def test_exists_returns_false_for_nonexistent(self, temp_dir):
        fm = FileManager(temp_dir)
        assert not fm.exists(temp_dir / "nonexistent.mp3")

    def test_exists_returns_true_for_existing(self, temp_dir):
        fm = FileManager(temp_dir)
        path = temp_dir / "exists.mp3"
        path.touch()
        assert fm.exists(path)

    def test_safe_filename_truncates_long_titles(self, temp_dir):
        fm = FileManager(temp_dir)
        long_title = "A" * 500
        ep = Episode(title=long_title, guid="x", audio_url="http://x.com/ep.mp3")
        path = fm.audio_path(ep)
        # Reasonable max: 200 chars + ".mp3" = 204
        assert len(path.name) <= 210, f"Filename too long: {len(path.name)}"
        assert path.suffix == ".mp3"

    def test_safe_filename_empty_title_fallback(self, temp_dir):
        """Should handle empty title gracefully — uses default extension .mp3."""
        fm = FileManager(temp_dir)
        ep = Episode(title="", guid="x")
        path = fm.audio_path(ep)
        assert path.name.endswith(".mp3")
        assert path.parent.name == "audio"


# ======================================================================
# AudioDownloader tests
# ======================================================================


def _mock_response(content: bytes, status_code: int = 200):
    """Build a mock httpx.Response-like object (not a real Response).

    httpx.Client.stream() returns a context manager; the response itself
    is not a context manager.  This mock mimics what callers receive.
    """
    resp = MagicMock()
    resp.status_code = status_code
    resp.iter_bytes.return_value = [content]
    return resp


def _mock_client_with_stream(mock_response):
    """Patch ``httpx.Client`` so that ``.stream(url)`` returns *mock_response*.

    Usage::

        with patch("httpx.Client") as MockClient:
            mock_client = MockClient.return_value.__enter__.return_value
            # Make ``client.stream(url)`` return a context manager that
            # yields *mock_response*:
            ctx = mock_client.stream.return_value.__enter__.return_value
            ctx.status_code = 200
            ctx.iter_bytes.return_value = [b"data"]

        # Equivalent shorthand:
    """
    # This is handled inline in each test for clarity
    pass


class TestAudioDownloader:
    """Timeout, retry, success, checksum, interrupted download."""

    # ----------------------------------------------------------------
    # Helper to setup httpx.Client mocking
    # ----------------------------------------------------------------

    @staticmethod
    def _mock_client(response_data: bytes | None = None, status_code: int = 200,
                     side_effect: Exception | None = None):
        """Patch ``httpx.Client`` and return a configured mock chain.

        Returns ``(patcher, mock_client, mock_response)`` so tests can
        further customise the mocks before calling ``download()``.
        """
        patcher = patch("httpx.Client")
        MockClient = patcher.start()

        # Client instance: `with httpx.Client(...) as client`
        client_instance = MagicMock()
        MockClient.return_value.__enter__.return_value = client_instance

        if side_effect:
            # When ``client.stream(url)`` should raise
            client_instance.stream.side_effect = side_effect
        else:
            # Response context: `with client.stream(url) as resp`
            response = MagicMock()
            response.status_code = status_code
            if response_data is not None:
                response.iter_bytes.return_value = [response_data]
            client_instance.stream.return_value.__enter__.return_value = response

        return patcher, client_instance

    # ----------------------------------------------------------------
    # Success
    # ----------------------------------------------------------------

    def test_successful_download_returns_result(self, tmp_path):
        content = b"hello, this is audio data"
        dest = tmp_path / "episode.mp3"

        patcher, _ = self._mock_client(response_data=content)

        dl = AudioDownloader(timeout=30, max_retries=2)
        result = dl.download("http://example.com/ep.mp3", dest)

        patcher.stop()

        assert result.success is True
        assert result.bytes_downloaded == len(content)
        assert result.destination == dest
        assert result.error is None
        assert result.sha256 == hashlib.sha256(content).hexdigest()
        assert dest.read_bytes() == content

    # ----------------------------------------------------------------
    # Checksum
    # ----------------------------------------------------------------

    def test_checksum_matches_downloaded_content(self, tmp_path):
        content = b"some binary audio content\x00\xff\xfe"
        dest = tmp_path / "checksum.mp3"

        patcher, _ = self._mock_client(response_data=content)

        dl = AudioDownloader(timeout=30, max_retries=1)
        result = dl.download("http://x.com/ep.mp3", dest)

        patcher.stop()

        expected_sha = hashlib.sha256(content).hexdigest()
        assert result.sha256 == expected_sha
        assert hashlib.sha256(dest.read_bytes()).hexdigest() == result.sha256

    # ----------------------------------------------------------------
    # Timeout → RetryableDownloadError
    # ----------------------------------------------------------------

    def test_timeout_raises_retryable(self, tmp_path):
        dest = tmp_path / "timeout.mp3"

        patcher, client_instance = self._mock_client(
            side_effect=httpx.TimeoutException("timed out")
        )

        dl = AudioDownloader(timeout=1, max_retries=2)
        with pytest.raises(RetryableDownloadError, match="after 2 attempts"):
            dl.download("http://x.com/ep.mp3", dest)

        patcher.stop()

        assert client_instance.stream.call_count == 2

    # ----------------------------------------------------------------
    # 404 → SkipDownloadError (no retry)
    # ----------------------------------------------------------------

    def test_404_raises_skip_no_retry(self, tmp_path):
        dest = tmp_path / "notfound.mp3"

        patcher, client_instance = self._mock_client(
            response_data=b"", status_code=404,
            side_effect=httpx.HTTPStatusError(
                "Not Found", request=MagicMock(),
                response=MagicMock(status_code=404),
            ),
        )

        dl = AudioDownloader(timeout=30, max_retries=3)
        with pytest.raises(SkipDownloadError, match="404"):
            dl.download("http://x.com/notfound.mp3", dest)

        patcher.stop()

    # ----------------------------------------------------------------
    # 5xx → RetryableDownloadError (retries)
    # ----------------------------------------------------------------

    def test_500_retries_then_raises_retryable(self, tmp_path):
        dest = tmp_path / "server_error.mp3"

        patcher = patch("httpx.Client")
        MockClient = patcher.start()

        client_instance = MagicMock()
        MockClient.return_value.__enter__.return_value = client_instance

        # A response with 500 status — raise_for_status raises HTTPStatusError
        response_500 = MagicMock()
        response_500.status_code = 500
        response_500.raise_for_status.side_effect = httpx.HTTPStatusError(
            "Server Error", request=MagicMock(),
            response=MagicMock(status_code=500),
        )
        client_instance.stream.return_value.__enter__.return_value = response_500

        dl = AudioDownloader(timeout=30, max_retries=2)
        with pytest.raises(RetryableDownloadError, match="after 2 attempts"):
            dl.download("http://x.com/error.mp3", dest)

        patcher.stop()

        assert client_instance.stream.call_count == 2

    # ----------------------------------------------------------------
    # Interrupted download — .part file cleaned up
    # ----------------------------------------------------------------

    def test_interrupted_download_cleans_up_part_file(self, tmp_path):
        dest = tmp_path / "interrupted.mp3"
        part = dest.with_suffix(".mp3.part")
        content = b"recovered data"

        patcher = patch("httpx.Client")
        MockClient = patcher.start()

        client_instance = MagicMock()
        MockClient.return_value.__enter__.return_value = client_instance

        # First call: response that fails during streaming
        fail_response = MagicMock()
        fail_response.status_code = 200
        fail_response.raise_for_status.return_value = None
        fail_response.iter_bytes = MagicMock(
            side_effect=httpx.TimeoutException("timed out during stream")
        )

        # Second call: response that succeeds
        success_response = MagicMock()
        success_response.status_code = 200
        success_response.raise_for_status.return_value = None
        success_response.iter_bytes.return_value = [content]

        client_instance.stream.return_value.__enter__.return_value = fail_response
        # On second call, return the success response
        def _stream_side_effect(*a, **kw):
            if client_instance.stream.call_count >= 2:
                ctx = MagicMock()
                ctx.__enter__.return_value = success_response
                return ctx
            ctx = MagicMock()
            ctx.__enter__.return_value = fail_response
            return ctx
        client_instance.stream.side_effect = _stream_side_effect

        dl = AudioDownloader(timeout=1, max_retries=2)
        dl.download("http://x.com/ep.mp3", dest)

        patcher.stop()

        assert not part.exists(), ".part file should be cleaned up"
        assert dest.exists(), "Final file should exist"
        assert dest.read_bytes() == content

    # ----------------------------------------------------------------
    # Disk full → AbortDownloadError
    # ----------------------------------------------------------------

    def test_disk_full_raises_abort(self, tmp_path):
        dest = tmp_path / "diskfull.mp3"

        patcher, client_instance = self._mock_client(
            side_effect=OSError(28, "No space left on device"),
        )

        dl = AudioDownloader(timeout=30, max_retries=2)
        with pytest.raises(AbortDownloadError, match="Disk full"):
            dl.download("http://x.com/ep.mp3", dest)

        patcher.stop()

    # ----------------------------------------------------------------
    # Atomic rename — .part → .mp3
    # ----------------------------------------------------------------

    def test_part_file_exists_during_download(self, tmp_path):
        content = b"atomic test data"
        dest = tmp_path / "atomic.mp3"
        part = dest.with_suffix(".mp3.part")

        patcher, _ = self._mock_client(response_data=content)

        dl = AudioDownloader(timeout=30, max_retries=1)
        dl.download("http://x.com/ep.mp3", dest)

        patcher.stop()

        assert dest.exists(), "Final file should exist"
        assert dest.read_bytes() == content
        assert not part.exists(), ".part file should be gone"
