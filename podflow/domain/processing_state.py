"""
Processing state machine for podcast episodes.

Each episode progresses through a linear pipeline.  The state enum
defines valid states and enforces that transitions follow the correct
sequence — an episode cannot skip stages (e.g., NEW → INDEXED).

Usage::

    >>> state = ProcessingState.NEW
    >>> state = state.transition_to(ProcessingState.DOWNLOADED)
    >>> state.can_transition_to(ProcessingState.SUMMARIZED)  # False (needs TRANSCRIBED first)
"""

from __future__ import annotations

from enum import Enum


class ProcessingState(str, Enum):
    """Ordered states an episode moves through during its lifecycle."""

    NEW = "NEW"
    """Episode metadata has been persisted but no processing has started."""

    DOWNLOADED = "DOWNLOADED"
    """Audio file has been successfully downloaded to disk."""

    TRANSCRIBED = "TRANSCRIBED"
    """Speech-to-text transcription has been completed."""

    SUMMARIZED = "SUMMARIZED"
    """AI-generated summary of the episode content is available."""

    EMBEDDED = "EMBEDDED"
    """Text embeddings have been generated for semantic search."""

    INDEXED = "INDEXED"
    """Episode is searchable via the vector / full-text index."""

    COMPLETE = "COMPLETE"
    """All processing stages have finished successfully."""

    FAILED = "FAILED"
    """An unrecoverable error occurred during processing."""

    # ----------------------------------------------------------------
    # State machine helpers
    # ----------------------------------------------------------------

    def can_transition_to(self, target: ProcessingState) -> bool:
        """Check whether moving from *self* to *target* is valid.

        Rules:
            - FAILED is a valid target from any state.
            - Transitions must follow the linear order (no skipping).
            - COMPLETE is terminal (only FAILED can follow).
        """
        if self == ProcessingState.FAILED:
            return False  # Terminal — no recovery without explicit reset
        if target == ProcessingState.FAILED:
            return True   # Always allowed to fail
        if self == ProcessingState.COMPLETE:
            return False  # Terminal

        ordered = list(ProcessingState)
        try:
            return ordered.index(target) == ordered.index(self) + 1
        except ValueError:
            return False

    def transition_to(self, target: ProcessingState) -> ProcessingState:
        """Return *target* if the transition is valid, otherwise raise.

        Raises:
            ValueError: If the transition is not permitted.
        """
        if not self.can_transition_to(target):
            raise ValueError(
                f"Invalid state transition: {self.value} → {target.value}. "
                f"Expected next state: {self._next_state().value if self._next_state() else 'FAILED only'}."
            )
        return target

    def _next_state(self) -> ProcessingState | None:
        """Return the next sequential state, or ``None`` if terminal."""
        ordered = list(ProcessingState)
        try:
            idx = ordered.index(self)
            return ordered[idx + 1] if idx + 1 < len(ordered) else None
        except ValueError:
            return None

    @property
    def is_terminal(self) -> bool:
        """True if the state is an endpoint (COMPLETE or FAILED)."""
        return self in (ProcessingState.COMPLETE, ProcessingState.FAILED)

    @property
    def is_ok(self) -> bool:
        """True if the state is not FAILED."""
        return self != ProcessingState.FAILED
