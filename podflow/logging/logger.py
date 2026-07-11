"""
Structured logging for PodFlow.

Provides a ``get_logger`` helper that returns a pre-configured logger
with consistent formatting, level pulled from settings, and automatic
injection of ``request_id`` / ``correlation_id`` from ASGI middleware
context variables.

Usage::

    from podflow.logging.logger import get_logger
    logger = get_logger(__name__)
    logger.info("Processing episode %s", guid)

Log records emitted during a request automatically include the
``request_id`` and ``correlation_id`` fields (or ``"-"`` when
outside of a request context).
"""

import logging
import sys

from podflow.config.settings import settings


class _RequestContextFilter(logging.Filter):
    """Inject ``request_id`` and ``correlation_id`` from context vars."""

    def filter(self, record: logging.LogRecord) -> bool:
        # Import here to avoid circular imports at module level
        from podflow.api.middleware import get_correlation_id, get_request_id  # noqa: PLC0415

        record.request_id = get_request_id()
        record.correlation_id = get_correlation_id()
        return True


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for the given module name.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        A :class:`logging.Logger` with a stream handler, structured
        formatter, and request-context filter attached.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(settings.log_level.upper())

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | rid=%(request_id)s cid=%(correlation_id)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        handler.addFilter(_RequestContextFilter())

        logger.addHandler(handler)

    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    return logger
