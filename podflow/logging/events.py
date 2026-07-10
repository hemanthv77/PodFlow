"""
Structured workflow events.

Every important action in the pipeline emits a structured event through
the standard logger.  Events use a parseable ``key=value`` format so they
can be consumed by log aggregation tools, metrics systems, or custom
monitors without any additional infrastructure.

Usage::

    emit("ingest.completed", podcast="Talk Python", episodes=553, elapsed=4.6)

Produces::

    2026-07-10 12:00:00 | INFO  | podflow.events | event=ingest.completed podcast=Talk_Python episodes=553 elapsed=4.6

Events are always logged — they become the single source of truth for
"what happened" across all consumers (CLI, Airflow, FastAPI, metrics).
"""

from __future__ import annotations

from podflow.logging.logger import get_logger

logger = get_logger("podflow.events")

# Characters that break key=value parsing
_UNSAFE = str.maketrans(
    {
        " ": "_",
        "=": "-",
        '"': "",
        "\n": " ",
        "\r": " ",
    }
)


def emit(event_name: str, **kwargs) -> None:
    """Emit a structured workflow event.

    Args:
        event_name: Dot-separated event identifier, e.g.
            ``"ingest.completed"``, ``"download.episode.failed"``.
        **kwargs: Arbitrary key-value pairs attached to the event.
            Values are sanitised to ensure safe parsing.
    """
    parts = [f"event={event_name}"]
    for key, value in kwargs.items():
        if value is None:
            continue
        safe_val = str(value).translate(_UNSAFE)
        parts.append(f"{key}={safe_val}")

    logger.info(" ".join(parts))
