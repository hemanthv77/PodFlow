"""
SQLAlchemy ORM models for PodFlow.

Defines ``Podcast`` (a feed source) and ``Episode`` (an individual episode).
"""

from datetime import datetime

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, relationship


class Base(DeclarativeBase):
    """Declarative base for all PodFlow models."""


class Podcast(Base):
    """Represents a podcast feed being tracked.

    One row per unique feed source (RSS URL, YouTube channel, etc.).
    """

    __tablename__ = "podcasts"

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)

    # ---- Identity ----
    source_type: Mapped[str] = Column(
        String(20), default="RSS", nullable=False, index=True
    )
    """Source platform: RSS, YOUTUBE, SPOTIFY, APPLE_PODCASTS."""

    rss_url: Mapped[str] = Column(String(1000), unique=True, nullable=False)
    """Canonical feed / channel URL (unique across sources)."""

    # ---- Metadata ----
    title: Mapped[str] = Column(String(500), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    link: Mapped[str | None] = Column(String(1000), nullable=True)
    language: Mapped[str | None] = Column(String(50), nullable=True)
    image_url: Mapped[str | None] = Column(String(1000), nullable=True)
    author: Mapped[str | None] = Column(String(500), nullable=True)
    copyright: Mapped[str | None] = Column(String(500), nullable=True)
    category: Mapped[str | None] = Column(String(200), nullable=True)
    website: Mapped[str | None] = Column(String(1000), nullable=True)

    # ---- Timestamps ----
    last_checked_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    """When the feed was most recently polled."""

    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    episodes: Mapped[list["Episode"]] = relationship(
        "Episode", back_populates="podcast", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Podcast(id={self.id}, title='{self.title}')>"


class Episode(Base):
    """Represents a single podcast episode."""

    __tablename__ = "episodes"
    __table_args__ = (
        UniqueConstraint("podcast_id", "guid", name="uq_episode_guid_per_podcast"),
    )

    id: Mapped[int] = Column(Integer, primary_key=True, autoincrement=True)
    podcast_id: Mapped[int] = Column(
        Integer, ForeignKey("podcasts.id"), nullable=False
    )

    title: Mapped[str] = Column(String(500), nullable=False)
    description: Mapped[str | None] = Column(Text, nullable=True)
    guid: Mapped[str] = Column(String(500), nullable=False)
    link: Mapped[str | None] = Column(String(1000), nullable=True)
    audio_url: Mapped[str | None] = Column(String(1000), nullable=True)
    published_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    duration: Mapped[int | None] = Column(Integer, nullable=True)
    """Duration in seconds.  ``None`` if not provided by the feed."""

    # ---- File integrity ----
    file_hash: Mapped[str | None] = Column(String(64), nullable=True)
    """SHA-256 hex digest of the downloaded audio file (64 chars)."""

    file_size: Mapped[int | None] = Column(BigInteger, nullable=True)
    """Size of the downloaded audio file in bytes."""

    # ---- HTTP caching (for conditional GET on re-download) ----
    etag: Mapped[str | None] = Column(String(500), nullable=True)
    """HTTP ETag header value from the last successful download."""

    last_modified: Mapped[str | None] = Column(String(100), nullable=True)
    """HTTP Last-Modified header value from the last successful download."""

    # ---- Processing state machine ----
    processing_state: Mapped[str] = Column(
        String(20), default="NEW", nullable=False, index=True
    )
    """Current stage in the pipeline: NEW → DOWNLOADED → ... → COMPLETE."""

    local_path: Mapped[str | None] = Column(String(1000), nullable=True)
    """Path to the downloaded audio file (set when state ≥ DOWNLOADED)."""

    error_message: Mapped[str | None] = Column(Text, nullable=True)
    """Error details if the episode is in FAILED state."""

    # ---- Soft delete ----
    is_active: Mapped[bool] = Column(Boolean, default=True, nullable=False, index=True)
    """Whether the episode is considered active.  Set to ``False`` instead of hard-deleting."""

    deleted_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    """When the episode was soft-deleted, if applicable."""

    state_updated_at: Mapped[datetime | None] = Column(DateTime, nullable=True)
    """Timestamp of the most recent state transition."""

    created_at: Mapped[datetime] = Column(
        DateTime, default=datetime.utcnow, nullable=False
    )

    podcast: Mapped["Podcast"] = relationship("Podcast", back_populates="episodes")

    def __repr__(self) -> str:
        return f"<Episode(id={self.id}, title='{self.title}')>"
