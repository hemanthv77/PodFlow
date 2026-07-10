"""Domain objects for PodFlow — pure data, no framework dependencies."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum


class SourceType(str, Enum):
    """Identifies which platform a podcast feed originates from.

    Used to differentiate ingestion logic — RSS feeds are parsed with
    :class:`~podflow.ingestion.rss_reader.RSSFeedReader`, YouTube with
    a future ``YouTubeReader``, and so on.
    """

    RSS = "RSS"
    YOUTUBE = "YOUTUBE"
    SPOTIFY = "SPOTIFY"
    APPLE_PODCASTS = "APPLE_PODCASTS"


@dataclass
class Podcast:
    """Domain representation of a podcast feed.

    Independent of any persistence mechanism. This is what flows
    through the application, not the SQLAlchemy model.
    """

    rss_url: str
    title: str
    source_type: SourceType = SourceType.RSS
    description: str | None = None
    link: str | None = None
    language: str | None = None
    image_url: str | None = None
    author: str | None = None
    copyright: str | None = None
    category: str | None = None
    website: str | None = None
