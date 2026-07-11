"""API routes for RSS feed ingestion."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from podflow.api.dependencies import get_podcast_service
from podflow.api.schemas import IngestRequest, IngestResponse
from podflow.services.podcast_service import PodcastService

router = APIRouter(prefix="/ingestions", tags=["Ingestions"])


@router.post(
    "",
    response_model=IngestResponse,
    status_code=201,
    operation_id="create_ingestion",
    summary="Ingest RSS feed",
    description="Fetch an RSS feed, parse episodes, and persist new ones. Existing episodes (matched by GUID) are skipped.",
    responses={
        201: {"description": "Ingestion completed — new episodes persisted"},
        400: {"description": "Invalid request body"},
        422: {"description": "Validation error"},
        502: {"description": "Upstream RSS feed error"},
    },
)
def ingest_feed(
    body: IngestRequest,
    service: PodcastService = Depends(get_podcast_service),
) -> IngestResponse:
    """Create an ingestion run.

    Fetches the given RSS feed, parses episodes, and persists new ones.
    Existing episodes (matched by GUID) are silently skipped.
    """
    result = service.run(body.rss_url)
    return IngestResponse(
        podcast=result.podcast,
        episodes_found=result.episodes_found,
        new_episodes=result.new_episodes,
        skipped_episodes=result.skipped_episodes,
        duration_seconds=result.duration_seconds,
        errors=result.errors,
        success=result.success,
    )
