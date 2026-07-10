"""
Business-logic service for downloading episode audio assets.

This is where the download *workflow* lives — it knows the sequence:
query → resolve paths → download → persist state.  It does NOT know
HTTP details (AudioDownloader), filesystem details (FileManager), or
SQL details (EpisodeRepository).
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from podflow.config.settings import settings
from podflow.database.repository import EpisodeRepository
from podflow.database.session import SessionLocal
from podflow.domain.episode import Episode as DomainEpisode
from podflow.domain.processing_state import ProcessingState
from podflow.downloader.audio import AudioDownloader
from podflow.downloader.filesystem import FileManager
from podflow.logging.events import emit
from podflow.logging.logger import get_logger

logger = get_logger(__name__)


@dataclass
class DownloadStats:
    """Aggregate result of a batch download run.

    Attributes:
        episodes_checked: Total episodes queried for download.
        episodes_downloaded: Successfully downloaded in this run.
        episodes_skipped: Already on disk or had no audio URL.
        episodes_failed: Download failed after retries.
        total_bytes: Sum of bytes written in this run.
        duration_seconds: Wall-clock time for the entire batch.
        errors: Individual error messages for failed episodes.
    """

    episodes_checked: int
    episodes_downloaded: int
    episodes_skipped: int
    episodes_failed: int
    total_bytes: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return self.episodes_failed == 0 and len(self.errors) == 0


class DownloadService:
    """Orchestrates batch audio downloads for undownloaded episodes.

    Usage (zero-config)::

        service = DownloadService()
        stats = service.download_new_episodes()
        print(stats)

    Usage (dependency injection, for testing)::

        service = DownloadService(
            downloader=MockDownloader(),
            file_manager=FileManager(Path("/tmp")),
            episode_repo=EpisodeRepository(session),
        )
    """

    def __init__(
        self,
        *,
        downloader: AudioDownloader | None = None,
        file_manager: FileManager | None = None,
        episode_repo: EpisodeRepository | None = None,
    ) -> None:
        self._downloader = downloader or AudioDownloader(
            timeout=settings.download_timeout,
            max_retries=settings.download_max_retries,
        )
        self._fm = file_manager or FileManager(settings.download_path)
        self._episode_repo = episode_repo  # created lazily in run()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download_new_episodes(
        self,
        podcast_id: int | None = None,
        limit: int | None = None,
    ) -> DownloadStats:
        """Download audio for episodes in ``NEW`` state.

        Args:
            podcast_id: If provided, restrict to a single podcast.
            limit: Maximum number of episodes to download in this batch.
                   ``None`` means download everything available.

        Returns:
            A :class:`DownloadStats` summarising the batch.
        """
        started_at = time.monotonic()
        self._fm.ensure_directories()

        session = SessionLocal()
        try:
            repo = self._episode_repo or EpisodeRepository(session)

            episodes = repo.list_by_state(
                ProcessingState.DISCOVERED,
                podcast_id=podcast_id,
            )

            if limit is not None:
                episodes = episodes[:limit]

            checked = len(episodes)

            emit("download.batch.started", episodes=checked)

            downloaded = 0
            skipped = 0
            failed = 0
            total_bytes = 0
            errors: list[str] = []

            for db_episode in episodes:
                try:
                    status, byte_count = self._download_one_episode(db_episode, repo)
                    if status == "downloaded":
                        downloaded += 1
                        total_bytes += byte_count
                    else:
                        skipped += 1
                except Exception as exc:
                    failed += 1
                    emit(
                        "download.episode.failed",
                        episode=db_episode.title,
                        error=str(exc)[:100],
                    )
                    errors.append(f"[{db_episode.title}]: {exc}")
                    repo.update_state(
                        db_episode.id,
                        ProcessingState.FAILED_DOWNLOAD,
                        error_message=str(exc),
                        _bypass_validation=True,
                    )

            session.commit()

            elapsed = round(time.monotonic() - started_at, 2)
            logger.info(
                "Download batch complete: %d checked, %d downloaded, "
                "%d skipped, %d failed (%.2fs).",
                checked,
                downloaded,
                skipped,
                failed,
                elapsed,
            )

            emit(
                "download.batch.completed",
                checked=checked,
                downloaded=downloaded,
                skipped=skipped,
                failed=failed,
                bytes=total_bytes,
                elapsed=elapsed,
            )

            return DownloadStats(
                episodes_checked=checked,
                episodes_downloaded=downloaded,
                episodes_skipped=skipped,
                episodes_failed=failed,
                total_bytes=total_bytes,
                duration_seconds=elapsed,
                errors=errors,
            )

        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _download_one_episode(
        self,
        db_episode,
        repo: EpisodeRepository,
    ) -> tuple[str, int]:
        """Download audio for a single episode ORM row.

        Returns:
            ``("downloaded", byte_count)`` on success,
            ``("skipped", 0)`` if no audio URL or file already exists.

        Raises:
            Exception: Propagated to the batch handler on failure.
        """
        if not db_episode.audio_url:
            logger.info("No audio URL for episode '%s' — skipping.", db_episode.title)
            emit("download.episode.skipped", episode=db_episode.title, reason="no_audio_url")
            return ("skipped", 0)

        # Build a lightweight domain Episode for FileManager path resolution
        domain_ep = DomainEpisode(
            title=db_episode.title,
            guid=db_episode.guid,
            audio_url=db_episode.audio_url,
        )

        dest = self._fm.audio_path(domain_ep)

        if self._fm.exists(dest):
            logger.info("Audio already on disk: %s — skipping.", dest.name)
            # Read integrity data from existing file
            import hashlib

            file_hash = hashlib.sha256(dest.read_bytes()).hexdigest()
            file_size = dest.stat().st_size
            # Transition through intermediate states to maintain state-machine
            # consistency without actually downloading
            for state in (ProcessingState.QUEUED, ProcessingState.DOWNLOADING):
                repo.update_state(db_episode.id, state)
            repo.update_state(
                db_episode.id,
                ProcessingState.DOWNLOADED,
                local_path=str(dest),
                file_hash=file_hash,
                file_size=file_size,
            )
            emit("download.episode.skipped", episode=db_episode.title, reason="already_on_disk")
            return ("skipped", 0)

        emit("download.episode.started", episode=db_episode.title)

        # Transition: DISCOVERED → QUEUED → DOWNLOADING (observable stages)
        repo.update_state(db_episode.id, ProcessingState.QUEUED)
        repo.update_state(
            db_episode.id,
            ProcessingState.DOWNLOADING,
        )

        result = self._downloader.download(db_episode.audio_url, dest)

        repo.update_state(
            db_episode.id,
            ProcessingState.DOWNLOADED,
            local_path=str(result.destination),
            file_hash=result.sha256,
            file_size=result.bytes_downloaded,
        )

        emit(
            "download.episode.completed",
            episode=db_episode.title,
            bytes=result.bytes_downloaded,
            sha256=result.sha256[:12],
        )

        return ("downloaded", result.bytes_downloaded)
