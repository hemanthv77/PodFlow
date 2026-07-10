"""
Orchestration service for podcast ingestion.

This is the single entry point for the ingestion pipeline.  It wires
together the reader, parser, and repositories, and manages the database
session lifecycle.

Usage (zero-config)::

    from podflow.services.podcast_service import PodcastService

    service = PodcastService()
    result = service.run("https://talkpython.fm/episodes/rss")
    print(result)

Usage (dependency injection, for testing)::

    service = PodcastService(
        rss_reader=MockReader(),
        parser=MockParser(),
        podcast_repo=PodcastRepository(session),
        episode_repo=EpisodeRepository(session),
    )
"""

from __future__ import annotations

import time

from podflow.config.settings import settings
from podflow.database.repository import EpisodeRepository, PodcastRepository
from podflow.database.session import SessionLocal
from podflow.domain.episode import IngestionResult
from podflow.ingestion.episode_parser import FeedParser
from podflow.ingestion.rss_reader import RSSFeedReader
from podflow.logging.logger import get_logger

logger = get_logger(__name__)


class PodcastService:
    """Orchestrates podcast ingestion: fetch → parse → persist.

    All dependencies are optional — sensible defaults are created when
    omitted.  Pass mock implementations for testing.

    The service owns the database session lifecycle: it creates, commits,
    and closes the session within :meth:`run`.
    """

    def __init__(
        self,
        *,
        rss_reader: RSSFeedReader | None = None,
        parser: FeedParser | None = None,
        podcast_repo: PodcastRepository | None = None,
        episode_repo: EpisodeRepository | None = None,
    ) -> None:
        self._rss_reader = rss_reader or RSSFeedReader(
            timeout=settings.rss_fetch_timeout,
        )
        self._parser = parser or FeedParser()

        # Repositories need a session — created lazily in run() if not provided
        self._podcast_repo = podcast_repo
        self._episode_repo = episode_repo

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(self, rss_url: str) -> IngestionResult:
        """Execute the ingestion pipeline for a single RSS feed.

        Args:
            rss_url: The podcast RSS feed URL.

        Returns:
            An :class:`IngestionResult` summarising what happened.
        """
        started_at = time.monotonic()
        errors: list[str] = []

        # ---- 1. Fetch ----
        try:
            raw_feed = self._rss_reader.fetch(rss_url)
        except Exception as exc:
            logger.exception("Failed to fetch RSS feed: %s", rss_url)
            return IngestionResult(
                podcast="(unknown)",
                episodes_found=0,
                new_episodes=0,
                skipped_episodes=0,
                duration_seconds=round(time.monotonic() - started_at, 2),
                errors=[str(exc)],
            )

        # ---- 2. Parse ----
        podcast_domain, episodes = self._parser.parse(raw_feed)
        episodes_found = len(episodes)

        if not episodes:
            logger.info("No parseable episodes found for '%s'.", podcast_domain.title)
            return IngestionResult(
                podcast=podcast_domain.title,
                episodes_found=0,
                new_episodes=0,
                skipped_episodes=0,
                duration_seconds=round(time.monotonic() - started_at, 2),
            )

        # ---- 3 & 4. Persist podcast + episodes ----
        session = SessionLocal()
        try:
            podcast_repo = self._podcast_repo or PodcastRepository(session)
            episode_repo = self._episode_repo or EpisodeRepository(session)

            podcast = podcast_repo.get_or_create(
                rss_url=rss_url,
                source_type=podcast_domain.source_type,
                title=podcast_domain.title,
                description=podcast_domain.description,
                link=podcast_domain.link,
                language=podcast_domain.language,
                image_url=podcast_domain.image_url,
                author=podcast_domain.author,
                category=podcast_domain.category,
                copyright=podcast_domain.copyright,
                website=podcast_domain.website,
            )

            episodes_data = [
                {
                    "title": ep.title,
                    "guid": ep.guid,
                    "audio_url": ep.audio_url,
                    "description": ep.description,
                    "link": ep.link,
                    "published_at": ep.published_at,
                    "duration": ep.duration,
                }
                for ep in episodes
            ]
            new_episodes = episode_repo.bulk_upsert(podcast.id, episodes_data)

            session.commit()

            skipped = episodes_found - new_episodes
            elapsed = round(time.monotonic() - started_at, 2)

            logger.info(
                "Ingestion complete for '%s': %d found, %d new, %d skipped (%.2fs).",
                podcast_domain.title,
                episodes_found,
                new_episodes,
                skipped,
                elapsed,
            )

            return IngestionResult(
                podcast=podcast_domain.title,
                episodes_found=episodes_found,
                new_episodes=new_episodes,
                skipped_episodes=skipped,
                duration_seconds=elapsed,
                errors=errors,
            )

        except Exception as exc:
            session.rollback()
            logger.exception("Database error during ingestion.")
            errors.append(f"Database error: {exc}")
            return IngestionResult(
                podcast=podcast_domain.title,
                episodes_found=episodes_found,
                new_episodes=0,
                skipped_episodes=0,
                duration_seconds=round(time.monotonic() - started_at, 2),
                errors=errors,
            )
        finally:
            session.close()
