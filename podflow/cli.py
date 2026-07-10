"""
Command-line interface for PodFlow.

Exercises the same services that FastAPI will use — zero additional
abstraction.  Each command maps directly to a service call.

Usage::

    python -m podflow.cli pipeline https://talkpython.fm/episodes/rss
    python -m podflow.cli ingest https://talkpython.fm/episodes/rss
    python -m podflow.cli download --limit 2
"""

from __future__ import annotations

import argparse

from podflow.database.session import init_db
from podflow.services.download_service import DownloadService
from podflow.services.pipeline_service import PipelineService
from podflow.services.podcast_service import PodcastService


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="podflow",
        description="Podcast ingestion and asset management pipeline.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # ---- ingest ----
    ingest_parser = sub.add_parser("ingest", help="Ingest episodes from an RSS feed")
    ingest_parser.add_argument(
        "url",
        help="RSS feed URL (e.g. https://talkpython.fm/episodes/rss)",
    )

    # ---- download ----
    download_parser = sub.add_parser("download", help="Download audio for new episodes")
    download_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Maximum number of episodes to download (default: all)",
    )

    # ---- pipeline ----
    pipeline_parser = sub.add_parser(
        "pipeline", help="Run the full pipeline: ingest + download"
    )
    pipeline_parser.add_argument(
        "url",
        help="RSS feed URL",
    )
    pipeline_parser.add_argument(
        "--limit", "-l",
        type=int,
        default=None,
        help="Maximum number of episodes to download (default: all)",
    )

    return parser


def main(argv: list[str] | None = None) -> int:
    """Entry point for the CLI.

    Args:
        argv: Command-line arguments (defaults to ``sys.argv[1:]``).

    Returns:
        Exit code (0 = success, 1 = error).
    """
    parser = _build_parser()
    args = parser.parse_args(argv)

    init_db()
    success = True

    if args.command == "ingest":
        result = PodcastService().run(args.url)
        _print_ingestion(result)
        success = result.success

    elif args.command == "download":
        stats = DownloadService().download_new_episodes(limit=args.limit)
        _print_download(stats)
        success = stats.success

    elif args.command == "pipeline":
        report = PipelineService().run(args.url, download_limit=args.limit)
        _print_pipeline(report)
        success = report.success

    return 0 if success else 1


# ------------------------------------------------------------------
# Output formatters
# ------------------------------------------------------------------

def _print_ingestion(result) -> None:
    print(f"Podcast:     {result.podcast}")
    print(f"Discovered:  {result.episodes_found}")
    print(f"New:         {result.new_episodes}")
    print(f"Skipped:     {result.skipped_episodes}")
    print(f"Duration:    {result.duration_seconds:.2f}s")
    if result.errors:
        print(f"Errors:      {len(result.errors)}")
        for e in result.errors:
            print(f"  - {e}")
    print(f"Success:     {result.success}")


def _print_download(stats) -> None:
    print(f"Checked:     {stats.episodes_checked}")
    print(f"Downloaded:  {stats.episodes_downloaded}")
    print(f"Skipped:     {stats.episodes_skipped}")
    print(f"Failed:      {stats.episodes_failed}")
    print(f"Total bytes: {stats.total_bytes:,}")
    print(f"Duration:    {stats.duration_seconds:.2f}s")
    if stats.errors:
        print(f"Errors:      {len(stats.errors)}")
        for e in stats.errors:
            print(f"  - {e}")
    print(f"Success:     {stats.success}")


def _print_pipeline(report) -> None:
    print(f"Podcast:     {report.podcast}")
    print(f"Discovered:  {report.discovered}")
    print(f"Inserted:    {report.inserted}")
    print(f"Downloaded:  {report.downloaded}")
    print(f"Skipped:     {report.skipped}")
    print(f"Failed:      {report.failed}")
    print(f"Duration:    {report.total_duration:.2f}s")
    if report.errors:
        print(f"Errors:      {len(report.errors)}")
        for e in report.errors[:5]:
            print(f"  - {e}")
    print(f"Success:     {report.success}")


if __name__ == "__main__":
    raise SystemExit(main())
