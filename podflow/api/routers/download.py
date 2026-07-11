"""API routes for audio download."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from podflow.api.dependencies import get_download_service
from podflow.api.schemas import DownloadRequest, DownloadResponse
from podflow.services.download_service import DownloadService

router = APIRouter(prefix="/downloads", tags=["Downloads"])


@router.post(
    "",
    response_model=DownloadResponse,
    status_code=202,
    operation_id="create_download_batch",
    summary="Download episode audio",
    description="Download audio for episodes in the DISCOVERED state. Downloads are atomic with SHA-256 verification. Use `limit` to control batch size.",
    responses={
        202: {"description": "Download batch completed"},
        422: {"description": "Validation error"},
    },
)
def download_episodes(
    body: DownloadRequest,
    service: DownloadService = Depends(get_download_service),
) -> DownloadResponse:
    """Create a download batch.

    Downloads audio for episodes in the DISCOVERED state.
    Downloads are atomic with SHA-256 verification.
    """
    stats = service.download_new_episodes(limit=body.limit)
    return DownloadResponse(
        episodes_checked=stats.episodes_checked,
        episodes_downloaded=stats.episodes_downloaded,
        episodes_skipped=stats.episodes_skipped,
        episodes_failed=stats.episodes_failed,
        total_bytes=stats.total_bytes,
        duration_seconds=stats.duration_seconds,
        errors=stats.errors,
        success=stats.success,
    )
