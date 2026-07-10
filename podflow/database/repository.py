"""
Repository layer for database operations.

Provides a clean abstraction over SQLAlchemy queries so that business logic
does not need to interact with the ORM directly.
"""

from collections.abc import Sequence
from datetime import datetime

from sqlalchemy.orm import Session

from podflow.database.models import Episode, Podcast
from podflow.domain.podcast import SourceType
from podflow.domain.processing_state import ProcessingState
from podflow.logging.logger import get_logger

logger = get_logger(__name__)


class PodcastRepository:
    """CRUD operations for :class:`Podcast` records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(
        self,
        rss_url: str,
        source_type: SourceType = SourceType.RSS,
        **fields,
    ) -> Podcast:
        """Return an existing podcast by ``rss_url`` or create a new one.

        On an existing podcast, ``last_checked_at`` is bumped to now.

        Args:
            rss_url: The feed URL (used as the unique key).
            source_type: Platform this feed comes from.
            **fields: Additional fields to set when creating
                      (title, description, author, etc.).

        Returns:
            The existing or newly-created :class:`Podcast`.
        """
        podcast = self._session.query(Podcast).filter_by(rss_url=rss_url).one_or_none()
        if podcast is None:
            podcast = Podcast(
                rss_url=rss_url,
                source_type=source_type.value,
                **fields,
            )
            self._session.add(podcast)
            self._session.flush()
            logger.info("Created new podcast [%s]: %s", source_type.value, podcast.title)
        else:
            podcast.last_checked_at = datetime.utcnow()
            self._session.flush()
        return podcast

    def get_by_id(self, podcast_id: int) -> Podcast | None:
        """Return a podcast by primary key, or ``None``."""
        return self._session.get(Podcast, podcast_id)


class EpisodeRepository:
    """CRUD operations for :class:`Episode` records."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def bulk_upsert(self, podcast_id: int, episodes_data: list[dict]) -> int:
        """Insert new episodes for a podcast, skipping those whose GUID already exists.

        Args:
            podcast_id: The owning podcast's primary key.
            episodes_data: List of dicts with keys matching ``Episode`` columns
                           (title, guid, audio_url, published_at, duration, etc.).

        Returns:
            The number of *new* episodes inserted.
        """
        inserted = 0
        for data in episodes_data:
            existing = (
                self._session.query(Episode)
                .filter_by(podcast_id=podcast_id, guid=data["guid"])
                .one_or_none()
            )
            if existing is not None:
                continue

            episode = Episode(podcast_id=podcast_id, **data)
            self._session.add(episode)
            inserted += 1

        if inserted:
            self._session.flush()
            logger.info("Inserted %d new episode(s) for podcast_id=%d", inserted, podcast_id)
        return inserted

    def list_by_state(
        self,
        processing_state: ProcessingState,
        podcast_id: int | None = None,
    ) -> Sequence[Episode]:
        """Return *active* episodes in a given processing state.

        Soft-deleted episodes (``is_active=False``) are excluded.

        Args:
            processing_state: The state to filter by (e.g. ``ProcessingState.NEW``).
            podcast_id: If provided, restrict to a single podcast.

        Returns:
            Ordered list of matching :class:`Episode` rows.
        """
        q = self._session.query(Episode).filter_by(
            processing_state=processing_state.value,
            is_active=True,
        )
        if podcast_id is not None:
            q = q.filter_by(podcast_id=podcast_id)
        return q.order_by(Episode.published_at).all()

    def soft_delete(self, episode_id: int) -> Episode | None:
        """Soft-delete an episode by setting ``is_active=False``.

        Args:
            episode_id: Primary key of the episode.

        Returns:
            The updated :class:`Episode`, or ``None`` if not found.
        """
        episode = self._session.get(Episode, episode_id)
        if episode is None:
            logger.warning("Episode id=%d not found; cannot soft-delete.", episode_id)
            return None
        episode.is_active = False
        episode.deleted_at = datetime.utcnow()
        self._session.flush()
        logger.info("Soft-deleted episode id=%d.", episode_id)
        return episode

    def update_state(
        self,
        episode_id: int,
        new_state: ProcessingState,
        *,
        local_path: str | None = None,
        file_hash: str | None = None,
        file_size: int | None = None,
        error_message: str | None = None,
        _bypass_validation: bool = False,
    ) -> Episode | None:
        """Transition an episode to a new processing state.

        Validates the transition via :meth:`ProcessingState.transition_to`
        unless ``_bypass_validation`` is ``True`` (used for failure paths).

        Args:
            episode_id: Primary key of the episode.
            new_state: Target processing state.
            local_path: Filesystem path (set on DOWNLOADED transition).
            file_hash: SHA-256 hex digest (set on DOWNLOADED transition).
            file_size: File size in bytes (set on DOWNLOADED transition).
            error_message: Error details (set on FAILED transition).
            _bypass_validation: Skip the state-machine transition check.

        Returns:
            The updated :class:`Episode`, or ``None`` if not found.
        """
        episode = self._session.get(Episode, episode_id)
        if episode is None:
            logger.warning("Episode id=%d not found; cannot update state.", episode_id)
            return None

        current = ProcessingState(episode.processing_state)
        if not _bypass_validation:
            current.transition_to(new_state)  # raises ValueError if invalid

        episode.processing_state = new_state.value
        episode.state_updated_at = datetime.utcnow()

        if local_path is not None:
            episode.local_path = local_path
        if file_hash is not None:
            episode.file_hash = file_hash
        if file_size is not None:
            episode.file_size = file_size
        if error_message is not None:
            episode.error_message = error_message

        self._session.flush()
        logger.info(
            "Episode id=%d: %s → %s",
            episode_id,
            current.value,
            new_state.value,
        )
        return episode
