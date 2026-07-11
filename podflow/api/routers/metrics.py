"""API routes for platform observability."""

from __future__ import annotations

import platform
import sys

from fastapi import APIRouter, Depends

from podflow.api.dependencies import get_db
from podflow.api.schemas import InfoResponse, MetricsResponse
from podflow.config.settings import settings
from podflow.services.metrics_service import MetricsService

router = APIRouter(tags=["Platform"])


@router.get(
    "/metrics",
    response_model=MetricsResponse,
    operation_id="get_metrics",
    summary="Platform metrics",
    description="Return operational metrics: podcast/episode counts, database size, download size, uptime.",
    responses={200: {"description": "Current platform metrics"}},
)
def get_metrics(db=Depends(get_db)) -> MetricsResponse:
    """Return platform operational metrics."""
    svc = MetricsService(db)
    return MetricsResponse(**svc.gather())


@router.get(
    "/info",
    response_model=InfoResponse,
    operation_id="get_info",
    summary="Application info",
    description="Return application identity: name, version, Python version, platform.",
    responses={200: {"description": "Application information"}},
)
def get_info() -> InfoResponse:
    """Return application identity information."""
    return InfoResponse(
        application=settings.app_name,
        version="0.5.0",
        python_version=sys.version.split()[0],
        platform=platform.system(),
        database_backend=settings.db_backend,
        api_version=settings.api_version,
    )
