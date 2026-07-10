"""
Structured logging for PodFlow.

Provides a `get_logger` helper that returns a pre-configured logger
with consistent formatting and level pulled from settings.
"""

import logging
import sys

from podflow.config.settings import settings


def get_logger(name: str) -> logging.Logger:
    """Return a logger configured for the given module name.

    Args:
        name: Typically ``__name__`` from the calling module.

    Returns:
        A :class:`logging.Logger` with a stream handler attached.
    """
    logger = logging.getLogger(name)

    # Avoid adding duplicate handlers on repeated calls
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(settings.log_level.upper())

        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
        handler.setFormatter(formatter)
        logger.addHandler(handler)

    logger.setLevel(settings.log_level.upper())
    logger.propagate = False
    return logger
