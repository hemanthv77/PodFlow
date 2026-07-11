"""API routes for podcast pipeline operations."""

from __future__ import annotations

from fastapi import APIRouter, Depends

from podflow.api.dependencies import get_pipeline_service
from podflow.api.schemas import PipelineRunRequest, PipelineRunResponse
from podflow.services.pipeline_service import PipelineService

router = APIRouter(prefix="/pipeline-executions", tags=["Pipeline Executions"])


@router.post(
    "",
    response_model=PipelineRunResponse,
    status_code=202,
    operation_id="create_pipeline_execution",
    summary="Run pipeline",
    description="Execute the full pipeline: ingest an RSS feed and download audio for new episodes. Returns a summary report.",
    responses={
        202: {"description": "Pipeline execution completed"},
        400: {"description": "Invalid request body"},
        422: {"description": "Validation error"},
        502: {"description": "Upstream RSS feed error"},
    },
)
def run_pipeline(
    body: PipelineRunRequest,
    service: PipelineService = Depends(get_pipeline_service),
) -> PipelineRunResponse:
    """Create a pipeline execution.

    Ingests the given RSS feed and downloads audio for new episodes.
    Returns immediately with the result of the run.
    """
    report = service.run(body.rss_url, download_limit=body.download_limit)
    return PipelineRunResponse(
        podcast=report.podcast,
        discovered=report.discovered,
        inserted=report.inserted,
        downloaded=report.downloaded,
        skipped=report.skipped,
        failed=report.failed,
        elapsed=report.elapsed,
        errors=report.errors,
        success=report.success,
    )
