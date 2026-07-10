"""
Workflow orchestrator for the full podcast pipeline.

Coordinates ingestion (PodcastService) and asset acquisition
(DownloadService) into a single, observable workflow.  It contains
zero business logic — it sequences capabilities and aggregates results.

Usage::

    from podflow.services.pipeline_service import PipelineService

    result = PipelineService().run("https://talkpython.fm/episodes/rss")
    print(result)
"""

from __future__ import annotations

import time

from podflow.domain.pipeline import PipelineReport
from podflow.services.download_service import DownloadService
from podflow.services.podcast_service import PodcastService
from podflow.logging.events import emit
from podflow.logging.logger import get_logger

logger = get_logger(__name__)


class PipelineService:
    """Orchestrates the end-to-end podcast workflow.

    Sequences::

        PodcastService.run(url)       → ingest feed
        DownloadService.run()         → download audio for new episodes

    Future::

        TranscriptionService.run()    → transcribe audio
        SummaryService.run()          → summarise transcripts

    All dependencies are optional — sensible defaults are created when
    omitted.  Pass mocks for testing.
    """

    def __init__(
        self,
        *,
        podcast_service: PodcastService | None = None,
        download_service: DownloadService | None = None,
    ) -> None:
        self._ingest = podcast_service or PodcastService()
        self._download = download_service or DownloadService()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def run(
        self,
        feed_url: str,
        *,
        download_limit: int | None = None,
    ) -> PipelineReport:
        """Execute the full pipeline for a single RSS feed.

        Args:
            feed_url: The podcast RSS feed URL.
            download_limit: Maximum number of episodes to download
                in this run.  ``None`` means download everything that
                was newly inserted.

        Returns:
            A :class:`PipelineReport` composing the sub-results.
        """
        started_at = time.monotonic()
        errors: list[str] = []

        emit("pipeline.started", url=feed_url)

        # ---- 1. Ingest ----
        logger.info("Pipeline stage 1/2: Ingesting %s ...", feed_url)
        ingest_result = self._ingest.run(feed_url)

        if not ingest_result.success:
            errors.extend(ingest_result.errors)
            logger.warning(
                "Ingestion returned errors: %s", ingest_result.errors
            )

        emit(
            "ingest.completed",
            podcast=ingest_result.podcast,
            found=ingest_result.episodes_found,
            inserted=ingest_result.new_episodes,
            elapsed=round(time.monotonic() - started_at, 2),
        )

        # ---- Early exit when nothing to download ----
        if ingest_result.new_episodes == 0:
            logger.info(
                "No new episodes to download for '%s'.",
                ingest_result.podcast,
            )
            elapsed = round(time.monotonic() - started_at, 2)
            report = PipelineReport(
                ingestion=ingest_result,
                download=None,
                total_duration=elapsed,
                errors=errors,
            )
            emit(
                "pipeline.completed",
                podcast=report.podcast,
                discovered=report.discovered,
                inserted=report.inserted,
                downloaded=report.downloaded,
                skipped=report.skipped,
                elapsed=report.elapsed,
            )
            return report

        # ---- 2. Download ----
        logger.info(
            "Pipeline stage 2/2: Downloading up to %s episode(s) ...",
            download_limit or "all available",
        )
        download_stats = self._download.download_new_episodes(limit=download_limit)

        errors.extend(download_stats.errors)
        elapsed = round(time.monotonic() - started_at, 2)

        report = PipelineReport(
            ingestion=ingest_result,
            download=download_stats,
            total_duration=elapsed,
            errors=errors,
        )

        emit(
            "pipeline.completed",
            podcast=report.podcast,
            discovered=report.discovered,
            inserted=report.inserted,
            downloaded=report.downloaded,
            skipped=report.skipped,
            failed=report.failed,
            elapsed=report.elapsed,
        )

        logger.info(
            "Pipeline complete for '%s': %d discovered, %d inserted, "
            "%d downloaded, %d skipped, %d failed (%.2fs).",
            report.podcast,
            report.discovered,
            report.inserted,
            report.downloaded,
            report.skipped,
            report.failed,
            report.elapsed,
        )

        return report
