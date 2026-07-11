"""API routes for podcast queries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from podflow.api.dependencies import get_db
from podflow.api.schemas import PodcastListResponse, PodcastResponse
from podflow.services.podcast_query_service import PodcastQueryService

router = APIRouter(prefix="/podcasts", tags=["Podcasts"])


@router.get(
    "",
    response_model=PodcastListResponse,
    operation_id="list_podcasts",
    summary="List podcasts",
    description="Return a paginated list of podcasts. Supports sorting and optional filtering by source type.",
    responses={
        200: {"description": "Paginated list of podcasts"},
        422: {"description": "Invalid query parameters"},
    },
)
def list_podcasts(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="title"),
    source_type: str | None = Query(default=None),
    db=Depends(get_db),
) -> PodcastListResponse:
    """List podcasts with pagination, sorting, and optional filtering."""
    svc = PodcastQueryService(db)
    result = svc.list_podcasts(offset=offset, limit=limit, sort_by=sort_by, source_type=source_type)
    return PodcastListResponse(
        items=[PodcastResponse.model_validate(r) for r in result.items],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.get(
    "/{podcast_id}",
    response_model=PodcastResponse,
    operation_id="get_podcast",
    summary="Get a podcast",
    description="Return a single podcast by its unique identifier.",
    responses={
        200: {"description": "Podcast found"},
        404: {"description": "Podcast not found"},
    },
)
def get_podcast(
    podcast_id: int,
    db=Depends(get_db),
) -> PodcastResponse:
    """Get a single podcast by ID."""
    svc = PodcastQueryService(db)
    row = svc.get_podcast(podcast_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Podcast not found")
    return PodcastResponse.model_validate(row)
