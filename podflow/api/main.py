"""FastAPI application factory and middleware stack.

Production-grade ASGI application with:

* Request ID generation (``X-Request-ID``)
* Correlation ID propagation (``X-Correlation-ID``)
* Security headers (``X-Content-Type-Options``, ``X-Frame-Options``, etc.)
* GZip compression (configurable minimum size)
* Structured request logging (method, path, status, duration, client IP)
* RFC 7807 error responses
* Graceful startup / shutdown
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse

from podflow.api.middleware import (
    CorrelationIDMiddleware,
    RequestIDMiddleware,
    RequestLoggingMiddleware,
    SecurityHeadersMiddleware,
    get_correlation_id,
    get_request_id,
)
from podflow.config.settings import settings
from podflow.database.session import engine, init_db
from podflow.exceptions.exceptions import (
    AbortDownloadError,
    DatabaseError,
    DownloadError,
    FilesystemError,
    PodFlowError,
    RetryableDownloadError,
    RSSFetchError,
    RSSParseError,
    SkipDownloadError,
)
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# ------------------------------------------------------------------
# Exception → HTTP status & title mapping
# ------------------------------------------------------------------

_STATUS_MAP: dict[type[PodFlowError], tuple[int, str]] = {
    RSSFetchError: (502, "RSS Fetch Error"),
    RSSParseError: (502, "RSS Parse Error"),
    DownloadError: (502, "Download Error"),
    RetryableDownloadError: (502, "Download Error"),
    SkipDownloadError: (404, "Not Found"),
    AbortDownloadError: (507, "Insufficient Storage"),
    FilesystemError: (500, "Filesystem Error"),
    DatabaseError: (500, "Database Error"),
}


def _http_status(exc: PodFlowError) -> tuple[int, str]:
    """Return (status_code, title) for a PodFlowError."""
    for cls, (status, title) in _STATUS_MAP.items():
        if isinstance(exc, cls):
            return status, title
    return 500, "Internal Error"


# ------------------------------------------------------------------
# Lifespan
# ------------------------------------------------------------------


@asynccontextmanager
async def _lifespan(app: FastAPI) -> AsyncIterator[None]:
    logger.info(
        "Starting PodFlow API on %s:%d (version=%s, db=%s) ...",
        settings.api_host,
        settings.api_port,
        settings.api_version,
        settings.db_backend,
    )
    init_db()
    logger.info("Database initialised — accepting requests")
    yield
    logger.info("Shutting down PodFlow API — draining active requests ...")
    engine.dispose()
    logger.info("Database engine disposed — shutdown complete")


# ------------------------------------------------------------------
# App factory
# ------------------------------------------------------------------


def create_app() -> FastAPI:
    """Build and configure the FastAPI application.

    Returns a fully-configured app instance ready for ``uvicorn.run()``
    or ASGI deployment.  Callers can further customise the returned
    instance (e.g. mount additional routers).
    """
    app = FastAPI(
        title=settings.app_name,
        version="0.5.0",
        description="""
PodFlow is a podcast ingestion and asset management platform.

## Capabilities

- **Ingest** RSS feeds into the episode catalog
- **Download** audio with SHA-256 integrity verification
- **Query** podcasts, episodes with filtering and pagination
- **Observe** platform health via metrics and info endpoints

## Processing Pipeline

Episodes move through an 18-state processing pipeline:
`DISCOVERED → QUEUED → DOWNLOADING → DOWNLOADED → ... → COMPLETE`

Each stage has a corresponding `FAILED_*` state for selective retries.

## Pagination

All list endpoints support `offset` and `limit` query parameters.
Default limit is 50, maximum is 500.

## Request Tracing

Every response includes `X-Request-ID` and `X-Correlation-ID` headers.
Clients may send `X-Correlation-ID` to propagate a trace across services.

## Errors

The API uses RFC 7807 problem details.  All error responses have
`type`, `title`, `status`, `detail`, `instance`, `request_id`,
and `correlation_id` fields.
""",
        contact={
            "name": "PodFlow Maintainers",
            "url": "https://github.com/hemanthv77/PodFlow",
        },
        license_info={
            "name": "MIT",
        },
        terms_of_service="https://github.com/hemanthv77/PodFlow",
        lifespan=_lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    # ---- Middleware (order matters — outermost first) ----
    _setup_cors(app)
    _setup_security_headers(app)
    _setup_gzip(app)
    _setup_request_id(app)
    _setup_correlation_id(app)
    _setup_request_logging(app)

    # ---- OpenAPI tags ----
    app.openapi_tags = [
        {
            "name": "Pipeline Executions",
            "description": "Full pipeline runs: ingest + download in one operation.",
        },
        {
            "name": "Ingestions",
            "description": "RSS feed ingestion — discover and persist new episodes.",
        },
        {"name": "Downloads", "description": "Audio download with SHA-256 integrity verification."},
        {"name": "Podcasts", "description": "Query tracked podcast feeds."},
        {"name": "Episodes", "description": "Query episodes with filtering by processing state."},
        {"name": "Platform", "description": "Operational metrics, health, readiness, version."},
    ]

    # ---- Exception handlers ----
    _setup_exception_handlers(app)

    # ---- Routes ----
    _include_routers(app)

    # ---- Platform endpoints ----
    _register_platform_endpoints(app)

    return app


# ------------------------------------------------------------------
# Route registration
# ------------------------------------------------------------------


def _include_routers(app: FastAPI) -> None:
    prefix = settings.api_prefix  # e.g. /api/v1

    from podflow.api.routers.download import router as download_router
    from podflow.api.routers.episodes import router as episodes_router
    from podflow.api.routers.ingest import router as ingest_router
    from podflow.api.routers.metrics import router as metrics_router
    from podflow.api.routers.pipeline import router as pipeline_router
    from podflow.api.routers.podcasts import router as podcasts_router

    app.include_router(ingest_router, prefix=prefix)
    app.include_router(download_router, prefix=prefix)
    app.include_router(pipeline_router, prefix=prefix)
    app.include_router(podcasts_router, prefix=prefix)
    app.include_router(episodes_router, prefix=prefix)
    app.include_router(metrics_router, prefix=prefix)


def _register_platform_endpoints(app: FastAPI) -> None:
    @app.get("/health")
    async def health() -> dict[str, str]:
        """Application is alive."""
        return {"status": "ok"}

    @app.get("/ready")
    async def ready() -> dict[str, str]:
        """Application is ready — database and dependencies reachable."""
        from sqlalchemy import text

        from podflow.database.session import SessionLocal

        try:
            session = SessionLocal()
            session.execute(text("SELECT 1"))
            session.close()
            return {"status": "ready", "database": "connected"}
        except Exception as exc:
            return {"status": "not ready", "database": str(exc)}

    @app.get("/version")
    async def version() -> dict[str, str]:
        """Application version information."""
        import subprocess

        git_sha = ""
        try:
            git_sha = (
                subprocess.check_output(
                    ["git", "rev-parse", "--short", "HEAD"],
                    stderr=subprocess.DEVNULL,
                )
                .decode()
                .strip()
            )
        except Exception:
            git_sha = "unknown"

        return {
            "app": settings.app_name,
            "version": "0.5.0",
            "api_version": settings.api_version,
            "git_sha": git_sha,
            "python": "3.12",
        }


# ------------------------------------------------------------------
# Middleware setup helpers
# ------------------------------------------------------------------


def _setup_cors(app: FastAPI) -> None:
    origins = [o.strip() for o in settings.cors_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins if origins != ["*"] else ["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )


def _setup_security_headers(app: FastAPI) -> None:
    app.add_middleware(SecurityHeadersMiddleware)


def _setup_gzip(app: FastAPI) -> None:
    app.add_middleware(GZipMiddleware, minimum_size=settings.gzip_min_size)


def _setup_request_id(app: FastAPI) -> None:
    app.add_middleware(RequestIDMiddleware)


def _setup_correlation_id(app: FastAPI) -> None:
    app.add_middleware(CorrelationIDMiddleware)


def _setup_request_logging(app: FastAPI) -> None:
    app.add_middleware(RequestLoggingMiddleware)


# ------------------------------------------------------------------
# Exception handlers
# ------------------------------------------------------------------


def _setup_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(PodFlowError)
    async def _podflow_error(request: Request, exc: PodFlowError) -> JSONResponse:
        status, title = _http_status(exc)
        logger.error(
            "PodFlowError [%d] %s → %s",
            status,
            request.url.path,
            exc,
        )
        return JSONResponse(
            status_code=status,
            content={
                "type": f"https://errors.podflow.dev/{type(exc).__name__.lower()}",
                "title": title,
                "status": status,
                "detail": str(exc),
                "instance": str(request.url.path),
                "request_id": get_request_id(),
                "correlation_id": get_correlation_id(),
            },
        )

    @app.exception_handler(Exception)
    async def _unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "Unhandled error on %s %s",
            request.method,
            request.url.path,
        )
        return JSONResponse(
            status_code=500,
            content={
                "type": "https://errors.podflow.dev/internal-error",
                "title": "Internal Server Error",
                "status": 500,
                "detail": "An unexpected error occurred. The incident has been logged.",
                "instance": str(request.url.path),
                "request_id": get_request_id(),
                "correlation_id": get_correlation_id(),
            },
        )

    @app.exception_handler(404)
    async def _not_found(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=404,
            content={
                "type": "https://errors.podflow.dev/not-found",
                "title": "Not Found",
                "status": 404,
                "detail": f"The path '{request.url.path}' was not found on this server.",
                "instance": str(request.url.path),
                "request_id": get_request_id(),
                "correlation_id": get_correlation_id(),
            },
        )

    @app.exception_handler(405)
    async def _method_not_allowed(request: Request, exc: Exception) -> JSONResponse:
        return JSONResponse(
            status_code=405,
            content={
                "type": "https://errors.podflow.dev/method-not-allowed",
                "title": "Method Not Allowed",
                "status": 405,
                "detail": f"Method {request.method} is not allowed for '{request.url.path}'.",
                "instance": str(request.url.path),
                "request_id": get_request_id(),
                "correlation_id": get_correlation_id(),
            },
        )


# ------------------------------------------------------------------
# Entry point
# ------------------------------------------------------------------


def run() -> None:
    """Start the FastAPI server via ``uvicorn``.

    Invoked via the ``podflow-api`` console script::

        podflow-api
    """
    import uvicorn

    uvicorn.run(
        "podflow.api.main:create_app",
        host=settings.api_host,
        port=settings.api_port,
        factory=True,
        reload=False,
    )
