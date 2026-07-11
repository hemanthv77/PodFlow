"""API routes for episode queries."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from podflow.api.dependencies import get_db
from podflow.api.schemas import EpisodeListResponse, EpisodeResponse
from podflow.services.episode_query_service import EpisodeQueryService

router = APIRouter(prefix="/episodes", tags=["Episodes"])


@router.get(
    "",
    response_model=EpisodeListResponse,
    operation_id="list_episodes",
    summary="List episodes",
    description="Return a paginated, sorted list of episodes. Optionally filter by podcast or processing state. Default: newest first.",
    responses={
        200: {"description": "Paginated list of episodes"},
        422: {"description": "Invalid query parameters"},
    },
)
def list_episodes(
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=50, ge=1, le=500),
    sort_by: str = Query(default="-published_at"),
    podcast_id: int | None = Query(default=None),
    processing_state: str | None = Query(default=None),
    db=Depends(get_db),
) -> EpisodeListResponse:
    """List episodes with pagination, sorting, and optional filtering.

    Use ``sort_by=-published_at`` for newest first (default).
    Filter by ``podcast_id`` or ``processing_state``.
    Soft-deleted episodes are excluded by default.
    """
    svc = EpisodeQueryService(db)
    result = svc.list_episodes(
        offset=offset,
        limit=limit,
        sort_by=sort_by,
        podcast_id=podcast_id,
        processing_state=processing_state,
    )
    return EpisodeListResponse(
        items=[EpisodeResponse.model_validate(r) for r in result.items],
        total=result.total,
        offset=result.offset,
        limit=result.limit,
    )


@router.get(
    "/{episode_id}",
    response_model=EpisodeResponse,
    operation_id="get_episode",
    summary="Get an episode",
    description="Return a single episode by its unique identifier.",
    responses={
        200: {"description": "Episode found"},
        404: {"description": "Episode not found"},
    },
)
def get_episode(
    episode_id: int,
    db=Depends(get_db),
) -> EpisodeResponse:
    """Get a single episode by ID."""
    svc = EpisodeQueryService(db)
    row = svc.get_episode(episode_id)
    if row is None:
        raise HTTPException(status_code=404, detail="Episode not found")
    return EpisodeResponse.model_validate(row)
