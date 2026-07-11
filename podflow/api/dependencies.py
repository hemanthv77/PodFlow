"""FastAPI dependency injection.

Each dependency yields a fully-wired service or session.  Services can
be overridden in tests by replacing the dependency provider.
"""

from __future__ import annotations

from collections.abc import Generator

from podflow.database.repository import EpisodeRepository, PodcastRepository
from podflow.database.session import SessionLocal
from podflow.services.download_service import DownloadService
from podflow.services.pipeline_service import PipelineService
from podflow.services.podcast_service import PodcastService


def get_podcast_service() -> PodcastService:
    """Return a default-configured PodcastService."""
    return PodcastService()


def get_download_service() -> DownloadService:
    """Return a default-configured DownloadService."""
    return DownloadService()


def get_pipeline_service() -> PipelineService:
    """Return a default-configured PipelineService."""
    return PipelineService()


def get_db() -> Generator:
    """Yield a database session, closing it after the request."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


def get_podcast_repo() -> Generator[PodcastRepository, None, None]:
    session = SessionLocal()
    try:
        yield PodcastRepository(session)
    finally:
        session.close()


def get_episode_repo() -> Generator[EpisodeRepository, None, None]:
    session = SessionLocal()
    try:
        yield EpisodeRepository(session)
    finally:
        session.close()
