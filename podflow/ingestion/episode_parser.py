"""
Parses a raw feedparser result into domain objects.

This is where ALL RSS-specific quirks belong — date formats, duration
parsing, audio URL extraction, missing field handling.  The rest of
the system never sees feedparser internals.

Input :  raw feedparser dict  (from :class:`RSSFeedReader.fetch`)
Output:  :class:`Podcast` + :class:`list[Episode]`
"""

from __future__ import annotations

import re
from datetime import datetime
from email.utils import parsedate_to_datetime
from typing import Any

from podflow.domain.episode import Episode
from podflow.domain.podcast import Podcast, SourceType
from podflow.exceptions.exceptions import MissingFieldError
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# ---- Duration patterns ----
_DURATION_HHMMSS = re.compile(r"^(\d+):([0-5]\d):([0-5]\d)$")
_DURATION_MMSS = re.compile(r"^(\d+):([0-5]\d)$")


class FeedParser:
    """Parses a raw feedparser result into domain objects.

    Usage::

        reader = RSSFeedReader()
        raw = reader.fetch("https://example.com/feed.xml")

        parser = FeedParser()
        podcast, episodes = parser.parse(raw)
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def parse(self, raw_feed: dict[str, Any]) -> tuple[Podcast, list[Episode]]:
        """Parse a raw feedparser result into domain objects.

        Args:
            raw_feed: The dict returned by :meth:`RSSFeedReader.fetch`.

        Returns:
            A ``(Podcast, list[Episode])`` tuple.  The episode list may
            be shorter than the raw entry count — malformed entries are
            logged and skipped.
        """
        feed = raw_feed.get("feed", {})
        entries = raw_feed.get("entries", [])

        podcast = self._parse_podcast(feed)
        episodes = self._parse_episodes(entries)

        logger.info(
            "Parsed feed '%s': %d / %d episodes valid.",
            podcast.title,
            len(episodes),
            len(entries),
        )
        return podcast, episodes

    # ------------------------------------------------------------------
    # Podcast extraction
    # ------------------------------------------------------------------

    def _parse_podcast(self, feed: dict[str, Any]) -> Podcast:
        """Extract podcast-level metadata from the ``<channel>`` block."""
        image = feed.get("image", {}) if isinstance(feed.get("image"), dict) else {}
        image_url = image.get("href") if image else None

        return Podcast(
            rss_url=feed.get("link", ""),
            title=feed.get("title", "Unknown Podcast"),
            source_type=SourceType.RSS,
            description=feed.get("subtitle") or feed.get("description"),
            link=feed.get("link"),
            language=feed.get("language"),
            image_url=image_url,
            author=feed.get("author"),
            category=feed.get("category"),
        )

    # ------------------------------------------------------------------
    # Episode extraction
    # ------------------------------------------------------------------

    def _parse_episodes(self, raw_entries: list[dict[str, Any]]) -> list[Episode]:
        """Parse every entry, skipping any that fail validation."""
        episodes: list[Episode] = []
        for entry in raw_entries:
            try:
                episodes.append(self._parse_one_episode(entry))
            except MissingFieldError as exc:
                logger.warning("Skipping entry: %s", exc)
        return episodes

    def _parse_one_episode(self, entry: dict[str, Any]) -> Episode:
        title = entry.get("title")
        if not title:
            raise MissingFieldError("Episode is missing required field: title")

        guid = entry.get("id") or entry.get("guid")
        if not guid:
            raise MissingFieldError(f"Episode '{title}' is missing required field: guid")

        return Episode(
            title=title.strip(),
            guid=str(guid).strip(),
            audio_url=self._extract_audio_url(entry),
            description=entry.get("summary") or entry.get("description"),
            link=entry.get("link"),
            published_at=self._parse_published(entry),
            duration=self._parse_duration(entry),
        )

    # ------------------------------------------------------------------
    # Field extractors  (RSS-specific quirks live here)
    # ------------------------------------------------------------------

    @staticmethod
    def _extract_audio_url(entry: dict[str, Any]) -> str | None:
        """Walk enclosures and media:content for the first audio URL."""
        # Primary: enclosures with audio MIME type
        for enc in entry.get("enclosures", []):
            mime = enc.get("type", "")
            href = enc.get("href")
            if href and mime.startswith("audio/"):
                return href

        # Some feeds use media:content instead of enclosures
        for media in entry.get("media_content", []):
            mime = media.get("type", "")
            url = media.get("url")
            if url and mime.startswith("audio/"):
                return url

        # Fallback: any enclosure with a recognisable audio extension
        for enc in entry.get("enclosures", []):
            href = enc.get("href", "")
            if href and any(href.lower().endswith(ext) for ext in (".mp3", ".m4a", ".ogg", ".wav")):
                return href

        return None

    @staticmethod
    def _parse_published(entry: dict[str, Any]) -> datetime | None:
        """Try multiple date formats commonly found in RSS feeds."""
        # feedparser provides a time.struct_time tuple
        published_parsed = entry.get("published_parsed")
        if published_parsed:
            try:
                return datetime(*published_parsed[:6])
            except (TypeError, ValueError):
                pass

        # Fallback to RFC 2822 string
        published_str = entry.get("published")
        if published_str:
            try:
                return parsedate_to_datetime(published_str)
            except (ValueError, TypeError):
                pass

        return None

    @staticmethod
    def _parse_duration(entry: dict[str, Any]) -> int | None:
        """Parse ``<itunes:duration>`` into total seconds.

        Handles:
            - ``HH:MM:SS``  → seconds
            - ``MM:SS``     → seconds
            - ``1234``      → raw integer seconds
        """
        raw = entry.get("itunes_duration") or entry.get("duration")
        if not raw:
            return None

        raw = str(raw).strip()

        # Integer seconds
        try:
            return int(raw)
        except ValueError:
            pass

        # HH:MM:SS
        match = _DURATION_HHMMSS.match(raw)
        if match:
            return int(match.group(1)) * 3600 + int(match.group(2)) * 60 + int(match.group(3))

        # MM:SS
        match = _DURATION_MMSS.match(raw)
        if match:
            return int(match.group(1)) * 60 + int(match.group(2))

        logger.debug("Unrecognized duration format: %r", raw)
        return None
