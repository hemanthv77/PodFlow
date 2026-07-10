"""Episode domain object — the canonical intermediate representation.

Every ingestion source (RSS, YouTube, etc.) must produce ``Episode``
instances.  Downstream consumers (database, downloader) only know
about this dataclass, never about feed-specific formats.
"""

from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class Episode:
    """A single podcast episode, parsed and validated.

    Attributes:
        title: Episode title.
        guid: Globally-unique identifier (from the feed's ``<guid>``).
        audio_url: Direct URL to the audio file.
        description: Episode description / show notes (may contain HTML).
        link: URL to the episode's web page.
        published_at: Publication timestamp.
        duration: Duration in seconds. ``None`` if not provided by the feed.
    """

    title: str
    guid: str
    audio_url: str | None = None
    description: str | None = None
    link: str | None = None
    published_at: datetime | None = None
    duration: int | None = None


@dataclass
class IngestionResult:
    """Summary returned by :meth:`PodcastService.run` after ingestion.

    Designed to be consumed by multiple clients — Airflow logs it,
    FastAPI serialises it to JSON, a GUI renders it, metrics systems
    scrape it.  One object, many consumers.

    Attributes:
        podcast: Display name of the ingested podcast.
        episodes_found: Total episodes parsed from the feed.
        new_episodes: Episodes that were *not* already in the database.
        skipped_episodes: Episodes already in the database (deduplicated).
        duration_seconds: Wall-clock time the ingestion run took.
        errors: Non-fatal error messages, if any.
    """

    podcast: str
    episodes_found: int
    new_episodes: int
    skipped_episodes: int
    duration_seconds: float
    errors: list[str] = field(default_factory=list)

    @property
    def success(self) -> bool:
        return len(self.errors) == 0
