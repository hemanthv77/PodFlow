"""Read-only query service for podcasts."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy.orm import Session

from podflow.database.models import Podcast


@dataclass
class PagedResult:
    """Generic paginated result container."""

    items: list
    total: int
    offset: int
    limit: int


class PodcastQueryService:
    """Read-only queries for podcasts.

    Owns pagination, sorting, and filtering logic.  Does not modify data.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_podcasts(
        self,
        offset: int = 0,
        limit: int = 50,
        sort_by: str = "title",
        source_type: str | None = None,
    ) -> PagedResult:
        """Return a paginated, sorted list of podcasts.

        Args:
            offset: Number of rows to skip.
            limit: Maximum rows to return (1–500).
            sort_by: Column to sort by (default: ``title``).
            source_type: Optional filter by ``source_type``.
        """
        q = self._session.query(Podcast)

        if source_type:
            q = q.filter_by(source_type=source_type.upper())

        total = q.count()

        sort_col = getattr(Podcast, sort_by, Podcast.title)
        rows = q.order_by(sort_col).offset(offset).limit(limit).all()

        return PagedResult(items=rows, total=total, offset=offset, limit=limit)

    def get_podcast(self, podcast_id: int) -> Podcast | None:
        """Return a single podcast by primary key, or ``None``."""
        return self._session.get(Podcast, podcast_id)

    def list_latest(self, limit: int = 10) -> list[Podcast]:
        """Return the most recently checked podcasts."""
        return (
            self._session.query(Podcast)
            .order_by(Podcast.last_checked_at.desc().nullslast())
            .limit(limit)
            .all()
        )
