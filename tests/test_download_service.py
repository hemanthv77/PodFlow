"""
Tests for DownloadService.

Uses mocked dependencies to verify the service correctly orchestrates
downloads and updates the database.
"""

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from podflow.database.models import Episode as EpisodeModel
from podflow.domain.processing_state import ProcessingState
from podflow.downloader.audio import DownloadResult
from podflow.downloader.filesystem import FileManager
from podflow.exceptions.exceptions import SkipDownloadError
from podflow.services.download_service import DownloadService


@pytest.fixture
def mock_db_episode():
    """Build a mock SQLAlchemy Episode ORM row."""
    ep = MagicMock(spec=EpisodeModel)
    ep.id = 1
    ep.title = "Test Episode"
    ep.guid = "guid-001"
    ep.audio_url = "https://example.com/audio.mp3"
    ep.processing_state = "NEW"
    return ep


@pytest.fixture
def mock_repo(mock_db_episode):
    """Build a mock EpisodeRepository."""
    repo = MagicMock()
    repo.list_by_state.return_value = [mock_db_episode]
    return repo


@pytest.fixture
def mock_downloader():
    """Build a mock AudioDownloader returning a successful result."""
    dl = MagicMock()
    dl.download.return_value = DownloadResult(
        success=True,
        bytes_downloaded=1_000_000,
        sha256="a" * 64,
        duration_seconds=2.5,
        destination=Path("/tmp/downloads/audio/Test Episode.mp3"),
    )
    return dl


@pytest.fixture
def mock_file_manager(tmp_path):
    """Build a mock FileManager."""
    fm = MagicMock(spec=FileManager)
    fm.audio_path.return_value = tmp_path / "audio" / "Test Episode.mp3"
    fm.exists.return_value = False
    return fm


class TestDownloadService:
    """Verify service orchestrates correctly with mocked dependencies."""

    # ----------------------------------------------------------------
    # Successful download
    # ----------------------------------------------------------------

    def test_download_success_updates_state(self, mock_repo, mock_downloader, mock_file_manager):
        service = DownloadService(
            downloader=mock_downloader,
            file_manager=mock_file_manager,
            episode_repo=mock_repo,
        )
        stats = service.download_new_episodes(limit=1)

        assert stats.episodes_checked == 1
        assert stats.episodes_downloaded == 1
        assert stats.episodes_failed == 0
        assert stats.episodes_skipped == 0
        assert stats.total_bytes == 1_000_000
        assert stats.success is True

        # Service now calls update_state 3x: QUEUED, DOWNLOADING, DOWNLOADED
        mock_repo.update_state.assert_any_call(
            1,
            ProcessingState.DOWNLOADED,
            local_path="/tmp/downloads/audio/Test Episode.mp3",
            file_hash="a" * 64,
            file_size=1_000_000,
        )

    # ----------------------------------------------------------------
    # No audio URL → skipped
    # ----------------------------------------------------------------

    def test_skip_episode_without_audio_url(self, mock_repo, mock_downloader, mock_file_manager):
        ep = MagicMock()
        ep.id = 2
        ep.title = "No Audio"
        ep.guid = "guid-002"
        ep.audio_url = None
        ep.processing_state = "NEW"
        mock_repo.list_by_state.return_value = [ep]

        service = DownloadService(
            downloader=mock_downloader,
            file_manager=mock_file_manager,
            episode_repo=mock_repo,
        )
        stats = service.download_new_episodes(limit=1)

        assert stats.episodes_checked == 1
        assert stats.episodes_skipped == 1
        assert stats.episodes_downloaded == 0

        # Downloader should NOT have been called
        mock_downloader.download.assert_not_called()

    # ----------------------------------------------------------------
    # Download failure → FAILED state
    # ----------------------------------------------------------------

    def test_download_failure_sets_failed_state(self, mock_repo, mock_file_manager):
        mock_downloader = MagicMock()
        mock_downloader.download.side_effect = SkipDownloadError("Episode gone (404)")

        service = DownloadService(
            downloader=mock_downloader,
            file_manager=mock_file_manager,
            episode_repo=mock_repo,
        )
        stats = service.download_new_episodes(limit=1)

        assert stats.episodes_checked == 1
        assert stats.episodes_downloaded == 0
        assert stats.episodes_failed == 1
        assert len(stats.errors) == 1
        assert "Episode gone" in stats.errors[0]

        # Service calls update_state for QUEUED, DOWNLOADING (before fail),
        # then FAILED_DOWNLOAD with bypass in the except handler
        mock_repo.update_state.assert_any_call(
            1,
            ProcessingState.FAILED_DOWNLOAD,
            error_message="Episode gone (404)",
            _bypass_validation=True,
        )

    # ----------------------------------------------------------------
    # Cache hit — file already exists
    # ----------------------------------------------------------------

    def test_skip_existing_file(
        self, mock_repo, mock_downloader, mock_file_manager, mock_db_episode, tmp_path
    ):
        # Create a real file on disk so the service can compute its SHA-256
        audio_dir = tmp_path / "audio"
        audio_dir.mkdir(parents=True)
        existing_file = audio_dir / "Test Episode.mp3"
        existing_file.write_text("fake audio content")

        mock_file_manager.audio_path.return_value = existing_file
        mock_file_manager.exists.return_value = True  # file already on disk

        service = DownloadService(
            downloader=mock_downloader,
            file_manager=mock_file_manager,
            episode_repo=mock_repo,
        )
        stats = service.download_new_episodes(limit=1)

        assert stats.episodes_checked == 1
        assert stats.episodes_skipped == 1
        assert stats.episodes_downloaded == 0

        # Downloader should NOT download again
        mock_downloader.download.assert_not_called()

        # Service transitions QUEUED → DOWNLOADING → DOWNLOADED for cache hits
        mock_repo.update_state.assert_any_call(
            1,
            ProcessingState.QUEUED,
        )
        mock_repo.update_state.assert_any_call(
            1,
            ProcessingState.DOWNLOADING,
        )
        call_kwargs = mock_repo.update_state.call_args_list[-1][1]
        assert call_kwargs["local_path"] is not None
        assert call_kwargs["file_hash"] is not None
        assert call_kwargs["file_size"] is not None

    # ----------------------------------------------------------------
    # Batch limit
    # ----------------------------------------------------------------

    def test_limit_respects_batch_size(self, mock_repo, mock_downloader, mock_file_manager):
        # Return 10 episodes
        mock_repo.list_by_state.return_value = [
            MagicMock(
                id=i,
                title=f"Ep {i}",
                guid=f"g-{i}",
                audio_url=f"http://x.com/{i}.mp3",
                processing_state="NEW",
            )
            for i in range(10)
        ]

        service = DownloadService(
            downloader=mock_downloader,
            file_manager=mock_file_manager,
            episode_repo=mock_repo,
        )
        stats = service.download_new_episodes(limit=3)

        assert stats.episodes_checked == 3
        assert stats.episodes_downloaded == 3
        assert mock_downloader.download.call_count == 3

    # ----------------------------------------------------------------
    # DownloadStats properties
    # ----------------------------------------------------------------

    def test_download_stats_success_property(self):
        from podflow.services.download_service import DownloadStats

        success = DownloadStats(
            episodes_checked=10,
            episodes_downloaded=10,
            episodes_skipped=0,
            episodes_failed=0,
            total_bytes=1000,
            duration_seconds=5.0,
            errors=[],
        )
        assert success.success is True

        failed = DownloadStats(
            episodes_checked=10,
            episodes_downloaded=9,
            episodes_skipped=0,
            episodes_failed=1,
            total_bytes=900,
            duration_seconds=5.0,
            errors=["[Ep 5]: Connection error"],
        )
        assert failed.success is False
