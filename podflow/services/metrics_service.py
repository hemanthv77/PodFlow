"""Platform metrics and uptime tracking.

Owns all operational calculations.  Routers call this service — they
do not touch databases, filesystems, or counters directly.
"""

from __future__ import annotations

import time
from pathlib import Path

from podflow.config.settings import settings
from podflow.domain.processing_state import ProcessingState

_started_at: float = time.monotonic()


class MetricsService:
    """Calculates platform-wide operational metrics."""

    def __init__(self, session) -> None:
        self._session = session

    def gather(self) -> dict:
        """Collect all metrics into a single dict.

        Returns a dictionary ready for serialisation by the router.
        Keys are stable — routers / consumers depend on them.
        """
        from podflow.database.models import Episode, Podcast

        podcast_count = self._session.query(Podcast).count()
        episode_count = self._session.query(Episode).filter_by(is_active=True).count()

        downloaded = (
            self._session.query(Episode)
            .filter_by(is_active=True, processing_state=ProcessingState.DOWNLOADED.value)
            .count()
        )
        failed_downloads = (
            self._session.query(Episode)
            .filter_by(is_active=True, processing_state=ProcessingState.FAILED_DOWNLOAD.value)
            .count()
        )

        db_path = Path(settings.database_path)
        db_size = round(db_path.stat().st_size / (1024 * 1024), 2) if db_path.exists() else 0.0

        dl_path = settings.download_path
        dl_size = round(_dir_size(dl_path) / (1024 * 1024), 2) if dl_path.exists() else 0.0

        uptime = round(time.monotonic() - _started_at, 1)

        return {
            "podcasts": podcast_count,
            "episodes": episode_count,
            "downloaded_episodes": downloaded,
            "failed_downloads": failed_downloads,
            "database_backend": settings.db_backend,
            "database_size_mb": db_size,
            "downloads_size_mb": dl_size,
            "uptime_seconds": uptime,
        }


def uptime_seconds() -> float:
    """Return the number of seconds since the application started."""
    return round(time.monotonic() - _started_at, 1)


def _dir_size(path: Path) -> int:
    """Recursively sum file sizes in *path*.  Returns 0 on error."""
    try:
        return sum(f.stat().st_size for f in path.rglob("*") if f.is_file())
    except OSError:
        return 0
