"""Pydantic request/response DTOs for the PodFlow API.

These are *transport* models — they define the API contract.  Domain
objects (podflow.domain.*) and ORM models (podflow.database.models.*)
are never exposed directly through the API.
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator

# ======================================================================
# Common
# ======================================================================


class ErrorResponse(BaseModel):
    """Standard error envelope — RFC 7807 inspired.

    Every error response returned by the API follows this shape so
    clients can reliably parse failures.
    """

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "type": "https://errors.podflow.dev/not-found",
                "title": "Not Found",
                "status": 404,
                "detail": "Podcast with id=999 was not found.",
                "instance": "/api/v1/podcasts/999",
                "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
            }
        }
    )

    type: str = Field(
        default="about:blank", description="URI reference identifying the problem type"
    )
    title: str = Field(description="Short, human-readable summary of the problem")
    status: int = Field(description="HTTP status code")
    detail: str = Field(description="Human-readable explanation specific to this occurrence")
    instance: str | None = Field(
        default=None, description="URI of the request that caused the error"
    )
    request_id: str = Field(default="-", description="``X-Request-ID`` assigned to this request")
    correlation_id: str = Field(
        default="-", description="``X-Correlation-ID`` for distributed tracing"
    )


class PaginationParams(BaseModel):
    """Query parameters for paginated list endpoints."""

    offset: int = Field(default=0, ge=0, description="Number of items to skip")
    limit: int = Field(default=50, ge=1, le=500, description="Maximum items per page (1–500)")


# ======================================================================
# Podcast
# ======================================================================


class PodcastResponse(BaseModel):
    """A podcast feed tracked by PodFlow."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "source_type": "RSS",
                "title": "Talk Python To Me",
                "description": "Python conversations for passionate developers",
                "link": "https://talkpython.fm",
                "language": "en-us",
                "image_url": "https://cdn.talkpython.fm/img/cover.png",
                "author": "Michael Kennedy",
                "category": "Technology",
                "rss_url": "https://talkpython.fm/episodes/rss",
                "last_checked_at": "2026-07-10T12:00:00",
                "created_at": "2026-07-10T00:00:00",
            }
        },
    )

    id: int = Field(description="Unique podcast identifier")
    source_type: str = Field(description="Source platform: RSS, YOUTUBE, SPOTIFY, APPLE_PODCASTS")
    title: str = Field(description="Podcast title")
    description: str | None = Field(default=None, description="Podcast description or subtitle")
    link: str | None = Field(default=None, description="Podcast website URL")
    language: str | None = Field(default=None, description="ISO language code (e.g. en-us)")
    image_url: str | None = Field(default=None, description="Cover artwork image URL")
    author: str | None = Field(default=None, description="Podcast author or creator")
    category: str | None = Field(default=None, description="Podcast category")
    rss_url: str = Field(description="Canonical RSS feed URL")
    last_checked_at: datetime | None = Field(
        default=None, description="When the feed was last polled"
    )
    created_at: datetime = Field(description="When this podcast was first added")


class PodcastListResponse(BaseModel):
    """Paginated list of podcasts."""

    items: list[PodcastResponse]
    total: int
    offset: int
    limit: int


# ======================================================================
# Episode
# ======================================================================


class EpisodeResponse(BaseModel):
    """A podcast episode tracked through the processing pipeline."""

    model_config = ConfigDict(
        from_attributes=True,
        json_schema_extra={
            "example": {
                "id": 1,
                "podcast_id": 1,
                "title": "#554: Trustworthy AI in Healthcare",
                "description": "Discussion about AI in medical applications.",
                "guid": "126623d8-741e-4b14-bdca-a75ec70774f9",
                "link": "https://talkpython.fm/episodes/show/554",
                "audio_url": "https://example.com/ep554.mp3",
                "published_at": "2026-07-10T05:10:31",
                "duration": 3640,
                "processing_state": "DOWNLOADED",
                "local_path": "/downloads/audio/ep554.mp3",
                "file_size": 58462737,
                "state_updated_at": "2026-07-10T12:01:00",
                "created_at": "2026-07-10T12:00:00",
            }
        },
    )

    id: int = Field(description="Unique episode identifier")
    podcast_id: int = Field(description="Owning podcast identifier")
    title: str = Field(description="Episode title")
    description: str | None = Field(default=None, description="Show notes or episode summary")
    guid: str = Field(description="Globally unique identifier from the feed")
    link: str | None = Field(default=None, description="Episode web page URL")
    audio_url: str | None = Field(default=None, description="Direct URL to the audio file")
    published_at: datetime | None = Field(default=None, description="Publication timestamp")
    duration: int | None = Field(default=None, description="Duration in seconds")
    processing_state: str = Field(description="Current stage in the processing pipeline")
    local_path: str | None = Field(
        default=None, description="Local filesystem path to downloaded audio"
    )
    file_size: int | None = Field(default=None, description="Audio file size in bytes")
    state_updated_at: datetime | None = Field(
        default=None, description="When the processing state last changed"
    )
    created_at: datetime = Field(description="When this episode was first discovered")


class EpisodeListResponse(BaseModel):
    """Paginated list of episodes."""

    items: list[EpisodeResponse]
    total: int
    offset: int
    limit: int


# ======================================================================
# Pipeline
# ======================================================================


class PipelineRunRequest(BaseModel):
    """Request to trigger a pipeline run."""

    rss_url: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        pattern=r"^https?://",
        examples=["https://talkpython.fm/episodes/rss"],
        description="RSS feed URL to ingest",
    )
    download_limit: Annotated[
        int | None,
        Field(default=None, ge=1, le=1000, description="Max episodes to download"),
    ]

    @model_validator(mode="after")
    def _validate_url(self) -> PipelineRunRequest:
        """Sanity-check the URL looks like an RSS feed."""
        if not self.rss_url.lower().startswith(("http://", "https://")):
            raise ValueError("rss_url must start with http:// or https://")
        return self


class PipelineRunResponse(BaseModel):
    """Result of a pipeline run."""

    podcast: str
    discovered: int
    inserted: int
    downloaded: int
    skipped: int
    failed: int
    elapsed: float
    errors: list[str] = []
    success: bool


# ======================================================================
# Ingest
# ======================================================================


class IngestRequest(BaseModel):
    """Request to ingest an RSS feed."""

    rss_url: str = Field(
        ...,
        min_length=5,
        max_length=2000,
        pattern=r"^https?://",
        examples=["https://talkpython.fm/episodes/rss"],
        description="RSS feed URL to ingest",
    )


class IngestResponse(BaseModel):
    """Result of an ingestion run."""

    podcast: str
    episodes_found: int
    new_episodes: int
    skipped_episodes: int
    duration_seconds: float
    errors: list[str] = []
    success: bool


# ======================================================================
# Download
# ======================================================================


class DownloadRequest(BaseModel):
    """Request to download episode audio."""

    limit: Annotated[
        int | None,
        Field(default=None, ge=1, le=1000, description="Max episodes to download"),
    ]


class DownloadResponse(BaseModel):
    """Result of a download batch."""

    episodes_checked: int
    episodes_downloaded: int
    episodes_skipped: int
    episodes_failed: int
    total_bytes: int
    duration_seconds: float
    errors: list[str] = []
    success: bool


# ======================================================================
# Metrics & Info
# ======================================================================


class MetricsResponse(BaseModel):
    """Platform operational metrics."""

    podcasts: int
    episodes: int
    downloaded_episodes: int
    failed_downloads: int
    database_backend: str
    database_size_mb: float
    downloads_size_mb: float
    uptime_seconds: float


class InfoResponse(BaseModel):
    """Application identity information."""

    application: str
    version: str
    python_version: str
    platform: str
    database_backend: str
    api_version: str
