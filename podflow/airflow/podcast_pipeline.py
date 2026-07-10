"""
Airflow DAG — the thinnest possible orchestration layer.

Zero business logic.  Zero loops.  Zero SQL.  Zero downloads.
One call to :class:`PipelineService`, serialisable result to XCom.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.sdk import dag, task

from podflow.config.settings import settings
from podflow.services.pipeline_service import PipelineService


@dag(
    dag_id="podcast_pipeline",
    description="Ingest podcast RSS feed and download new episodes.",
    schedule=timedelta(hours=6),
    start_date=datetime(2026, 7, 1),
    catchup=False,
    tags=["podflow", "podcast"],
    max_active_runs=1,
)
def podcast_pipeline() -> None:
    """PodFlow main ingestion DAG."""

    @task(task_id="run_pipeline")
    def run_pipeline(rss_url: str = settings.rss_url) -> dict:
        report = PipelineService().run(rss_url)
        return {
            "podcast": report.podcast,
            "discovered": report.discovered,
            "inserted": report.inserted,
            "downloaded": report.downloaded,
            "skipped": report.skipped,
            "failed": report.failed,
            "duration_s": report.total_duration,
            "success": report.success,
            "errors": report.errors,
        }

    run_pipeline()


# Airflow discovers this via the DAG loader
podcast_pipeline_dag = podcast_pipeline()
