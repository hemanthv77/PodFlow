"""
Fetches and parses an RSS podcast feed.

Single responsibility: given a URL, return the raw, parsed feed data.
It knows nothing about podcast domain objects, episodes, databases, or downloads.

Returns the raw :class:`feedparser.FeedParserDict` — callers extract
whatever they need from it.
"""

from typing import Any

import feedparser

from podflow.exceptions.exceptions import RSSFetchError, RSSParseError
from podflow.logging.logger import get_logger

logger = get_logger(__name__)


class RSSFeedReader:
    """Downloads an RSS feed and returns the parsed result.

    Usage::

        reader = RSSFeedReader(timeout=30)
        raw_feed: dict[str, Any] = reader.fetch("https://example.com/feed.xml")
        # raw_feed["feed"]["title"]  → podcast title
        # raw_feed["entries"]        → list of episode dicts
    """

    def __init__(self, timeout: int = 30) -> None:
        """
        Args:
            timeout: HTTP request timeout in seconds.
        """
        self._timeout = timeout

    def fetch(self, url: str) -> dict[str, Any]:
        """Fetch the RSS feed at *url* and return the parsed result.

        Args:
            url: The RSS feed URL.

        Returns:
            A :class:`feedparser.FeedParserDict` (behaves like a dict)
            with top-level keys ``feed`` (channel metadata) and ``entries``
            (list of item dicts).

        Raises:
            RSSParseError: If the response body is not valid RSS/XML.
            RSSFetchError: If the feed contains no usable data (missing title,
                zero entries, or HTTP error).
        """
        logger.info("Fetching RSS feed: %s", url)

        parsed = feedparser.parse(
            url,
            request_headers={"User-Agent": "PodFlow/1.0"},
        )

        # feedparser sets bozo=1 when XML parsing fails
        if parsed.bozo:
            logger.error("RSS parse error for %s: %s", url, parsed.bozo_exception)
            raise RSSParseError(
                f"Failed to parse RSS feed at {url}: {parsed.bozo_exception}"
            )

        # A valid podcast feed must have a title — treat missing as a fetch failure
        feed = parsed.feed
        if not feed.get("title"):
            status = getattr(parsed, "status", None)
            raise RSSFetchError(
                f"No valid feed data at {url} (HTTP {status}). "
                "The URL may not point to a podcast RSS feed."
            )

        logger.info(
            "Fetched feed '%s': %d episode(s) found.",
            feed.get("title", "Unknown"),
            len(parsed.entries),
        )

        return parsed

