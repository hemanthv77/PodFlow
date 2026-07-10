"""
Downloads files via HTTP streaming with checksum verification.

Pure I/O component — given a URL and a destination path, it downloads
the file and returns a result.  It knows nothing about episodes,
podcasts, databases, or filesystem naming conventions.
"""

from __future__ import annotations

import errno
import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

import httpx

from podflow.exceptions.exceptions import (
    AbortDownloadError,
    DownloadError,
    RetryableDownloadError,
    SkipDownloadError,
)
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# Chunk size for streaming downloads (1 MB)
_CHUNK_SIZE = 1_024 * 1_024


@dataclass
class DownloadResult:
    """Outcome of a single download attempt.

    Attributes:
        success: ``True`` if the download completed without errors.
        bytes_downloaded: Total bytes written to disk.
        sha256: SHA-256 hex digest of the downloaded file.
        duration_seconds: Wall-clock time for the download.
        destination: The :class:`Path` the file was written to.
        error: Error message if ``success`` is ``False``.
    """

    success: bool
    bytes_downloaded: int
    sha256: str
    duration_seconds: float
    destination: Path
    error: str | None = None


class AudioDownloader:
    """Downloads a file from a URL to a local path via HTTP streaming.

    Responsibilities:
        - Stream download with configurable timeout.
        - Retry on transient failures.
        - Compute SHA-256 checksum during download.
        - Atomic writes (``.part`` → rename on success).
        - Clean up partial files on failure.

    NOT responsibilities:
        - Choosing filenames or directories (caller provides destination).
        - Updating any database.
        - Knowing about episodes or podcasts.

    Usage::

        dl = AudioDownloader(timeout=120, max_retries=3)
        result = dl.download(
            url="https://example.com/episode.mp3",
            destination=Path("downloads/audio/ep.mp3"),
        )
        print(result.sha256, result.bytes_downloaded)
    """

    def __init__(
        self,
        timeout: int = 120,
        max_retries: int = 3,
    ) -> None:
        """
        Args:
            timeout: HTTP request timeout in seconds.
            max_retries: Number of retry attempts for transient failures.
        """
        self._timeout = timeout
        self._max_retries = max_retries

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def download(self, url: str, destination: Path) -> DownloadResult:
        """Download *url* to *destination*.

        Error categories:
            - **Retryable** (timeout, 5xx, connection reset): retried up to
              ``max_retries`` times.
            - **Skip** (404, 410, gone): fails fast without retries.
            - **Abort** (disk full, permission denied): fails fast immediately.

        Args:
            url: The URL to download from.
            destination: Full path where the file should be written
                         (including filename).

        Returns:
            A :class:`DownloadResult` with outcome metadata.

        Raises:
            RetryableDownloadError: After exhausting all retry attempts.
            SkipDownloadError: For permanent episode-level failures (e.g. 404).
            AbortDownloadError: For fatal batch-level failures (e.g. disk full).
        """
        started_at = time.monotonic()
        last_error: Exception | None = None
        tmp = destination.with_suffix(destination.suffix + ".part")

        for attempt in range(1, self._max_retries + 1):
            try:
                logger.info(
                    "Downloading %s (attempt %d/%d) ...",
                    url,
                    attempt,
                    self._max_retries,
                )
                sha256, byte_count = self._stream_with_hash(url, tmp)

                # Atomic rename on success
                tmp.rename(destination)

                elapsed = round(time.monotonic() - started_at, 2)
                logger.info(
                    "Downloaded: %s (%d bytes, sha256=%s, %.2fs)",
                    destination.name,
                    byte_count,
                    sha256[:12],
                    elapsed,
                )

                return DownloadResult(
                    success=True,
                    bytes_downloaded=byte_count,
                    sha256=sha256,
                    duration_seconds=elapsed,
                    destination=destination,
                )

            except SkipDownloadError:
                # Permanent — fail immediately, no retry
                self._cleanup(tmp)
                raise

            except AbortDownloadError:
                # Fatal — fail immediately, no retry
                self._cleanup(tmp)
                raise

            except RetryableDownloadError as exc:
                last_error = exc
                logger.warning("Retryable error (attempt %d/%d): %s", attempt, self._max_retries, exc)
                self._cleanup(tmp)

            except (httpx.RequestError, httpx.HTTPStatusError, OSError) as exc:
                # Classify unknown errors
                categorized = self._categorize_error(exc, url)
                if isinstance(categorized, RetryableDownloadError):
                    last_error = exc
                    logger.warning("Retryable error (attempt %d/%d): %s", attempt, self._max_retries, exc)
                    self._cleanup(tmp)
                else:
                    self._cleanup(tmp)
                    raise categorized

        elapsed = round(time.monotonic() - started_at, 2)
        msg = f"Failed to download {url} after {self._max_retries} attempts ({elapsed:.2f}s)"
        logger.error(msg)
        raise RetryableDownloadError(msg) from last_error

    # ------------------------------------------------------------------
    # Error categorization
    # ------------------------------------------------------------------

    @staticmethod
    def _categorize_error(exc: Exception, url: str) -> DownloadError:
        """Map an exception to the right download error category."""
        # --- HTTP status codes ---
        if isinstance(exc, httpx.HTTPStatusError):
            status = exc.response.status_code
            if status in (404, 410):
                return SkipDownloadError(
                    f"Episode not found at {url} (HTTP {status})"
                )
            if 400 <= status < 500:
                return SkipDownloadError(
                    f"Client error for {url} (HTTP {status})"
                )
            if 500 <= status < 600:
                return RetryableDownloadError(
                    f"Server error for {url} (HTTP {status})"
                )

        # --- Timeouts ---
        if isinstance(exc, httpx.TimeoutException):
            return RetryableDownloadError(f"Timeout downloading {url}: {exc}")

        # --- Connection errors ---
        if isinstance(exc, httpx.ConnectError):
            return RetryableDownloadError(f"Connection failed for {url}: {exc}")

        # --- OS errors ---
        if isinstance(exc, PermissionError):
            return AbortDownloadError(
                f"Permission denied writing download: {exc}"
            )

        if isinstance(exc, OSError):
            if getattr(exc, "errno", None) == errno.ENOSPC:
                return AbortDownloadError(f"Disk full: {exc}")
            if getattr(exc, "errno", None) in (errno.EACCES, errno.EPERM):
                return AbortDownloadError(f"Permission denied: {exc}")
            return RetryableDownloadError(f"OS error downloading {url}: {exc}")

        # --- Fallback ---
        return RetryableDownloadError(f"Unexpected error downloading {url}: {exc}")

        elapsed = round(time.monotonic() - started_at, 2)
        msg = f"Failed to download {url} after {self._max_retries} attempts ({elapsed:.2f}s)"
        logger.error(msg)
        raise RetryableDownloadError(msg) from last_error

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _stream_with_hash(self, url: str, dest: Path) -> tuple[str, int]:
        """Stream *url* to *dest*, returning ``(sha256_hex, byte_count)``."""
        sha = hashlib.sha256()
        byte_count = 0

        with httpx.Client(timeout=self._timeout, follow_redirects=True) as client:
            with client.stream("GET", url) as response:
                response.raise_for_status()

                dest.parent.mkdir(parents=True, exist_ok=True)

                with open(dest, "wb") as f:
                    for chunk in response.iter_bytes(chunk_size=_CHUNK_SIZE):
                        f.write(chunk)
                        sha.update(chunk)
                        byte_count += len(chunk)

        return sha.hexdigest(), byte_count

    @staticmethod
    def _cleanup(path: Path) -> None:
        """Delete *path* if it exists (partial or temp file)."""
        try:
            path.unlink(missing_ok=True)
        except OSError:
            pass
