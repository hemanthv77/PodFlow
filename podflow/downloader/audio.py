"""
Downloads podcast episode audio files via HTTP streaming.

Handles retries, partial-download cleanup, and delegates filesystem
decisions to :class:`FileManager`.
"""

from pathlib import Path

import httpx

from podflow.domain.episode import Episode
from podflow.downloader.filesystem import FileManager
from podflow.exceptions.exceptions import DownloadError
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# Chunk size for streaming downloads (1 MB)
_CHUNK_SIZE = 1_024 * 1_024


class AudioDownloader:
    """Downloads podcast audio files via HTTP(S).

    Delegates path generation and existence checks to :class:`FileManager`
    so that naming conventions are not duplicated here.

    Usage::

        fm = FileManager(download_dir=Path("downloads"))
        dl = AudioDownloader(file_manager=fm, timeout=120, max_retries=3)
        local_path = dl.download(episode)
    """

    def __init__(
        self,
        file_manager: FileManager,
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        """
        Args:
            file_manager: Filesystem abstraction for path resolution.
            timeout: HTTP request timeout in seconds.
            max_retries: Number of retry attempts for transient failures.
        """
        self._fm = file_manager
        self._timeout = timeout
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(self, episode: Episode) -> Path | None:
        """Download the audio file for *episode*.

        Skips download if the file already exists on disk.  Skips
        silently if the episode has no ``audio_url``.

        Args:
            episode: The episode to download audio for.

        Returns:
            The local :class:`Path` on success, or ``None`` if the
            episode had no audio URL or could not be downloaded.
        """
        if not episode.audio_url:
            logger.info("Episode '%s' has no audio URL — skipping download.", episode.title)
            return None

        dest = self._fm.episode_path(episode)

        if self._fm.exists(episode):
            logger.info("Audio already exists: %s — skipping.", dest.name)
            return dest

        return self._download_with_retry(episode.audio_url, dest, episode.title)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _download_with_retry(self, url: str, dest: Path, title: str) -> Path | None:
        last_error: Exception | None = None

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "Downloading '%s' (attempt %d/%d) ...",
                    title,
                    attempt,
                    self._max_retries,
                )
                self._stream_to_disk(url, dest)
                logger.info("Downloaded: %s (%s bytes)", dest.name, dest.stat().st_size)
                return dest
            except (httpx.RequestError, OSError) as exc:
                last_error = exc
                logger.warning("Download attempt %d failed: %s", attempt, exc)
                # Clean up partial file before retry
                self._cleanup_partial(dest)

        logger.error("All %d download attempts failed for '%s'.", self._max_retries, title)
        raise DownloadError(
            f"Failed to download '{title}' after {self._max_retries} attempts"
        ) from last_error

    def _stream_to_disk(self, url: str, dest: Path) -> None:
        """Stream *url* to *dest* using httpx with a timeout."""
        with httpx.Client(timeout=self._timeout) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()
                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        f.write(chunk)

    @staticmethod
    def _cleanup_partial(path: Path) -> None:
        """Delete a partially-downloaded file if it exists."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
