"""
Processing state machine for podcast episodes.

Each episode progresses through a linear pipeline with per-stage failure
states for observability and selective retries.

Usage::

    >>> s = ProcessingState.NEW
    >>> s.can_transition_to(ProcessingState.DISCOVERED)
    True
    >>> s.can_transition_to(ProcessingState.DOWNLOADING)
    False  # must go through DISCOVERED → QUEUED → DOWNLOADING
    >>> s.transition_to(ProcessingState.FAILED_DOWNLOAD)
    ValueError  # must go through DOWNLOADING first
"""

from __future__ import annotations

from enum import Enum


# Map: in-progress state value → failure state value
_FAILURE_TRANSITIONS: dict[str, str] = {
    "DOWNLOADING": "FAILED_DOWNLOAD",
    "TRANSCRIBING": "FAILED_TRANSCRIPTION",
    "SUMMARIZING": "FAILED_SUMMARIZATION",
    "EMBEDDING": "FAILED_EMBEDDING",
}


class ProcessingState(str, Enum):
    """Ordered states an episode moves through during its lifecycle.

    The order in this enum defines the valid linear progression.  Each
    stage has a corresponding ``FAILED_*`` state that is reachable only
    from that specific stage.
    """

    # ---- Ingestion ----
    NEW = "NEW"
    """Episode metadata has been persisted but no processing has started."""

    DISCOVERED = "DISCOVERED"
    """Episode has been validated and is ready for the next stage."""

    # ---- Download ----
    QUEUED = "QUEUED"
    """Episode has been enqueued for download."""

    DOWNLOADING = "DOWNLOADING"
    """Download is in progress."""

    DOWNLOADED = "DOWNLOADED"
    """Audio file has been successfully downloaded to disk."""

    FAILED_DOWNLOAD = "FAILED_DOWNLOAD"
    """Download failed after exhausting retries."""

    # ---- Transcription (future) ----
    TRANSCRIBING = "TRANSCRIBING"
    """Speech-to-text transcription is in progress."""

    TRANSCRIBED = "TRANSCRIBED"
    """Transcription has been completed."""

    FAILED_TRANSCRIPTION = "FAILED_TRANSCRIPTION"
    """Transcription failed."""

    # ---- Summarization (future) ----
    SUMMARIZING = "SUMMARIZING"
    """AI summarization is in progress."""

    SUMMARIZED = "SUMMARIZED"
    """Summary has been generated."""

    FAILED_SUMMARIZATION = "FAILED_SUMMARIZATION"
    """Summarization failed."""

    # ---- Embedding (future) ----
    EMBEDDING = "EMBEDDING"
    """Text embedding generation is in progress."""

    EMBEDDED = "EMBEDDED"
    """Embeddings have been computed."""

    FAILED_EMBEDDING = "FAILED_EMBEDDING"
    """Embedding generation failed."""

    # ---- Terminal ----
    COMPLETE = "COMPLETE"
    """All processing stages have finished successfully."""

    # ----------------------------------------------------------------
    # State machine helpers
    # ----------------------------------------------------------------

    def can_transition_to(self, target: ProcessingState) -> bool:
        """Check whether moving from *self* to *target* is valid.

        Rules:
            - A ``FAILED_*`` state is valid only if it matches the
              current in-progress stage (e.g. ``DOWNLOADING -> FAILED_DOWNLOAD``).
            - Transitions must follow the linear order (no skipping).
            - ``COMPLETE`` is terminal.
            - ``FAILED_*`` states are terminal.
        """
        # Terminal states
        if self.is_terminal:
            return False

        # Per-stage failure transitions — check the klass-level dict
        klass = self.__class__
        expected_failure: ProcessingState | None = None
        for in_progress, failed_state in _FAILURE_TRANSITIONS.items():
            if self.value == in_progress and target.value == failed_state:
                return True

        # Linear progression
        ordered = list(ProcessingState)
        try:
            self_idx = ordered.index(self)
            target_idx = ordered.index(target)
            return target_idx == self_idx + 1
        except ValueError:
            return False

    def transition_to(self, target: ProcessingState) -> ProcessingState:
        """Return *target* if the transition is valid, otherwise raise.

        Raises:
            ValueError: If the transition is not permitted.
        """
        if not self.can_transition_to(target):
            expected = self._next_state()
            expected_name = expected.value if expected else "(none)"
            raise ValueError(
                f"Invalid state transition: {self.value} → {target.value}. "
                f"Expected next state: {expected_name}."
            )
        return target

    def _next_state(self) -> ProcessingState | None:
        """Return the next sequential state, or ``None`` if terminal."""
        ordered = list(ProcessingState)
        try:
            idx = ordered.index(self)
            if idx + 1 < len(ordered):
                return ordered[idx + 1]
        except ValueError:
            pass
        return None

    @property
    def is_terminal(self) -> bool:
        """True if this is an endpoint (terminal success or per-stage failure)."""
        if self == ProcessingState.COMPLETE:
            return True
        return self.value.startswith("FAILED_")

    @property
    def is_ok(self) -> bool:
        """True if this is not a failure state."""
        return not self.value.startswith("FAILED_")
