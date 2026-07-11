"""Read-only query service for episodes."""

from __future__ import annotations

from sqlalchemy.orm import Session

from podflow.database.models import Episode
from podflow.services.podcast_query_service import PagedResult


class EpisodeQueryService:
    """Read-only queries for episodes.

    Owns pagination, sorting, and filtering logic.  Does not modify data.
    """

    def __init__(self, session: Session) -> None:
        self._session = session

    def list_episodes(
        self,
        offset: int = 0,
        limit: int = 50,
        sort_by: str = "published_at",
        podcast_id: int | None = None,
        processing_state: str | None = None,
        is_active: bool | None = True,
    ) -> PagedResult:
        """Return a paginated, sorted list of episodes.

        Args:
            offset: Number of rows to skip.
            limit: Maximum rows to return (1–500).
            sort_by: Column to sort by (default: ``published_at``).
            podcast_id: Optional filter by owning podcast.
            processing_state: Optional filter by processing state.
            is_active: If ``True``, exclude soft-deleted episodes (default).
        """
        q = self._session.query(Episode)

        if podcast_id is not None:
            q = q.filter_by(podcast_id=podcast_id)
        if processing_state:
            q = q.filter_by(processing_state=processing_state.upper())
        if is_active is not None:
            q = q.filter_by(is_active=is_active)

        total = q.count()

        # Sort: published_at descending by default
        reverse = sort_by.startswith("-")
        col_name = sort_by[1:] if reverse else sort_by
        sort_col = getattr(Episode, col_name, Episode.published_at)
        if reverse:
            sort_col = sort_col.desc()

        rows = q.order_by(sort_col).offset(offset).limit(limit).all()

        return PagedResult(items=rows, total=total, offset=offset, limit=limit)

    def get_episode(self, episode_id: int) -> Episode | None:
        """Return a single episode by primary key, or ``None``."""
        return self._session.get(Episode, episode_id)
