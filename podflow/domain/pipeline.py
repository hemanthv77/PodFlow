"""Workflow-level report composed from sub-service results."""

from __future__ import annotations

from dataclasses import dataclass, field

from podflow.domain.episode import IngestionResult
from podflow.services.download_service import DownloadStats


@dataclass
class PipelineReport:
    """Receipt for an entire pipeline run, composed from sub-results.

    Instead of flattening every counter into a single struct, this report
    embeds the original sub-results so consumers can access detail when
    they need it and ignore it when they don't.

    Top-level convenience properties (``podcast``, ``downloaded``, etc.)
    delegate to the embedded sub-results for quick access.

    Attributes:
        ingestion: The result from :class:`PodcastService.run()`.
        download: The stats from :class:`DownloadService.download_new_episodes()`.
        total_duration: Wall-clock time for the entire pipeline in seconds.
        errors: Aggregated error messages from both stages.
    """

    ingestion: IngestionResult
    download: DownloadStats | None = None
    total_duration: float = 0.0
    errors: list[str] = field(default_factory=list)

    # ------------------------------------------------------------------
    # Top-level convenience accessors
    # ------------------------------------------------------------------

    @property
    def podcast(self) -> str:
        return self.ingestion.podcast

    @property
    def discovered(self) -> int:
        return self.ingestion.episodes_found

    @property
    def inserted(self) -> int:
        return self.ingestion.new_episodes

    @property
    def downloaded(self) -> int:
        return self.download.episodes_downloaded if self.download else 0

    @property
    def skipped(self) -> int:
        """Episodes skipped during ingest OR download."""
        ingest_skipped = self.ingestion.skipped_episodes
        download_skipped = self.download.episodes_skipped if self.download else 0
        return ingest_skipped + download_skipped

    @property
    def failed(self) -> int:
        return self.download.episodes_failed if self.download else 0

    @property
    def elapsed(self) -> float:
        return self.total_duration

    @property
    def success(self) -> bool:
        """``True`` when no errors occurred and nothing failed."""
        return not (self.ingestion.errors or (self.download and self.download.errors))
