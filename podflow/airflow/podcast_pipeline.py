"""
Airflow DAG that orchestrates the PodFlow ingestion pipeline.

This DAG contains zero business logic — it only wires dependencies and
delegates to :class:`PodcastService`.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from airflow.sdk import dag, task

from podflow.config.settings import settings
from podflow.database.repository import EpisodeRepository, PodcastRepository
from podflow.database.session import SessionLocal
from podflow.downloader.audio import AudioDownloader
from podflow.downloader.filesystem import FileManager
from podflow.ingestion.episode_parser import EpisodeParser
from podflow.ingestion.rss_reader import RSSFeedReader
from podflow.services.podcast_service import PodcastService


@dag(
    dag_id="podcast_pipeline",
    description="Fetch, parse, store, and download podcast episodes.",
    schedule=timedelta(hours=6),
    start_date=datetime(2026, 7, 1),
    catchup=False,
    tags=["podflow", "podcast"],
    max_active_runs=1,
)
def podcast_pipeline() -> None:
    """PodFlow main ingestion DAG."""

    @task(task_id="ingest_podcast")
    def ingest_podcast(rss_url: str = settings.rss_url) -> dict:
        """Run the full pipeline and return a summary dict for XCom."""
        session = SessionLocal()

        try:
            service = PodcastService(
                rss_reader=RSSFeedReader(timeout=settings.rss_fetch_timeout),
                episode_parser=EpisodeParser(),
                audio_downloader=AudioDownloader(
                    file_manager=FileManager(settings.download_path),
                    timeout=settings.download_timeout,
                    max_retries=settings.download_max_retries,
                ),
                podcast_repo=PodcastRepository(session),
                episode_repo=EpisodeRepository(session),
            )

            result = service.run(rss_url)
            session.commit()

            return {
                "podcast": result.podcast_title,
                "found": result.episodes_found,
                "new": result.episodes_new,
                "downloaded": result.episodes_downloaded,
                "errors": result.errors,
            }
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()

    ingest_podcast()


# Instantiate the DAG so Airflow discovers it
podcast_pipeline_dag = podcast_pipeline()
