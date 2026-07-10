"""
Custom exception hierarchy for PodFlow.

All PodFlow-specific errors inherit from :class:`PodFlowError` so they
can be caught in a single ``except PodFlowError`` block at DAG level.
"""


class PodFlowError(Exception):
    """Base exception for all PodFlow errors."""


# ---- Ingestion ----


class IngestionError(PodFlowError):
    """Raised when fetching or reading a podcast feed fails."""


class RSSFetchError(IngestionError):
    """Raised when the HTTP request to an RSS feed fails."""


class RSSParseError(IngestionError):
    """Raised when the RSS/XML response cannot be parsed."""


# ---- Parsing ----


class ParseError(PodFlowError):
    """Raised when episode metadata extraction or validation fails."""


class MissingFieldError(ParseError):
    """Raised when a required field is absent from parsed episode data."""


class InvalidDataError(ParseError):
    """Raised when a field's value is invalid (e.g., non-numeric duration)."""


# ---- Download ----


class DownloadError(PodFlowError):
    """Base exception for download failures."""


class RetryableDownloadError(DownloadError):
    """Transient error — retrying may succeed (timeout, 5xx, connection reset)."""


class SkipDownloadError(DownloadError):
    """Permanent error for this episode — skip it (404, 410, gone)."""


class AbortDownloadError(DownloadError):
    """Fatal error — abort the entire batch (disk full, permission denied)."""


class FilesystemError(PodFlowError):
    """Raised when a filesystem operation (write, mkdir, etc.) fails."""


# ---- Database ----


class DatabaseError(PodFlowError):
    """Raised when a database operation fails."""
