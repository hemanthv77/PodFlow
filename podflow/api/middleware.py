"""ASGI middleware stack for the PodFlow API.

Each middleware is a discrete, testable unit.  They are wired into
the FastAPI application in :func:`podflow.api.main.create_app`.
"""

from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from podflow.config.settings import settings
from podflow.logging.logger import get_logger

logger = get_logger(__name__)

# ------------------------------------------------------------------
# Context variables — accessible from anywhere during a request
# ------------------------------------------------------------------

_request_id_var: ContextVar[str] = ContextVar("request_id", default="-")
_correlation_id_var: ContextVar[str] = ContextVar("correlation_id", default="-")


def get_request_id() -> str:
    """Return the current request ID from context, or ``"-"``."""
    return _request_id_var.get()


def get_correlation_id() -> str:
    """Return the current correlation ID from context, or ``"-"``."""
    return _correlation_id_var.get()


# ------------------------------------------------------------------
# 1. Request ID
# ------------------------------------------------------------------


class RequestIDMiddleware(BaseHTTPMiddleware):
    """Generate a unique ``X-Request-ID`` for every request.

    Stores the value in ``request.state.request_id`` and returns it
    in the ``X-Request-ID`` response header.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        rid = str(uuid.uuid4())
        request.state.request_id = rid
        _request_id_var.set(rid)

        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


# ------------------------------------------------------------------
# 2. Correlation ID
# ------------------------------------------------------------------


class CorrelationIDMiddleware(BaseHTTPMiddleware):
    """Accept or generate an ``X-Correlation-ID`` for tracing.

    If the client sends the header it is reused; otherwise a new UUID
    is created.  Stored in ``request.state.correlation_id`` and
    returned in the ``X-Correlation-ID`` response header.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        cid = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        request.state.correlation_id = cid
        _correlation_id_var.set(cid)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = cid
        return response


# ------------------------------------------------------------------
# 3. Security Headers
# ------------------------------------------------------------------


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    """Add baseline security headers to every response.

    Headers added:

    * ``X-Content-Type-Options: nosniff``
    * ``X-Frame-Options: DENY``
    * ``Referrer-Policy: no-referrer``
    * ``Permissions-Policy: `` (empty — deny all powerful features)
    * ``Strict-Transport-Security`` (only when ``settings.enable_https`` is True)
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)

        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "DENY")
        response.headers.setdefault("Referrer-Policy", "no-referrer")
        response.headers.setdefault("Permissions-Policy", "")

        if settings.enable_https:
            response.headers.setdefault(
                "Strict-Transport-Security",
                "max-age=31536000; includeSubDomains",
            )

        return response


# ------------------------------------------------------------------
# 4. Structured Request Logging
# ------------------------------------------------------------------


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """Log every request with structured metadata.

    One log line per request including method, path, status, duration,
    request_id, correlation_id, and client IP.
    """

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        started = time.monotonic()
        response = await call_next(request)
        elapsed_ms = (time.monotonic() - started) * 1000

        rid = getattr(request.state, "request_id", "-")
        cid = getattr(request.state, "correlation_id", "-")
        client_ip = _client_ip(request)

        logger.info(
            "%s %s → %d (%.1fms) | rid=%s cid=%s ip=%s",
            request.method,
            request.url.path,
            response.status_code,
            elapsed_ms,
            rid,
            cid,
            client_ip,
        )
        return response


# ------------------------------------------------------------------
# Helpers
# ------------------------------------------------------------------


def _client_ip(request: Request) -> str:
    """Extract the best-guess client IP from request headers."""
    forwarded: str | None = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    real_ip: str | None = request.headers.get("X-Real-IP")
    if real_ip:
        return real_ip
    if request.client and request.client.host:
        return str(request.client.host)
    return "unknown"
