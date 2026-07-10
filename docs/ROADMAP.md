# PodFlow Roadmap

> **Document version:** 1.0 — Phase 2 completion
> **Last updated:** 2026-07-10

## Overview

PodFlow is built in phases, each adding a layer of capability. Phases are designed so that each one produces a working, testable increment — the project is never in a broken state between phases.

---

## Completed Phases

### Phase 1 — Project Scaffolding

**Status:** ✅ Complete

- Project directory structure created.
- Apache Airflow 3.2 installed and configured (`LocalExecutor`, simple auth).
- Python virtual environment with all dependencies.
- `.env` configuration file with initial values.
- `.gitignore` rules established.
- Module stubs created for all planned packages.

### Phase 2 — Foundation Layer

**Status:** ✅ Complete

- **Configuration**: `podflow/config/settings.py` — pydantic-settings loading from `.env`.
- **Logging**: `podflow/logging/logger.py` — structured logging with `get_logger()`.
- **Exceptions**: `podflow/exceptions/exceptions.py` — typed hierarchy rooted at `PodFlowError`.
- **Database models**: `podflow/database/models.py` — `Podcast` and `Episode` SQLAlchemy models with constraints and indexes.
- **Database session**: `podflow/database/session.py` — engine, session factory, `init_db()`.
- **Database repository**: `podflow/database/repository.py` — `PodcastRepository` and `EpisodeRepository` with CRUD operations.
- **Domain objects**: `podflow/domain/` — `Podcast`, `Episode`, `PipelineResult`, `ProcessingState`, `SourceType`.
- **Schema evolution**: Added `source_type`, `file_hash`, `file_size`, `etag`, `last_modified`, `is_active`, `deleted_at`, and extended podcast metadata fields.
- **Processing state machine**: Enum with 8 states, validated transitions, terminal state enforcement.
- **Soft delete**: `is_active` flag with `deleted_at` timestamp on episodes.

### Phase 3 — Ingestion & Pipeline (Current)

**Status:** ✅ Complete

- **RSS reader**: `podflow/ingestion/rss_reader.py` — fetch and parse RSS feeds via `feedparser`.
- **Episode parser**: `podflow/ingestion/episode_parser.py` — raw RSS entries → `Episode` domain objects.
- **Audio downloader**: `podflow/downloader/audio.py` — HTTP streaming with retry logic.
- **File manager**: `podflow/downloader/filesystem.py` — safe filenames, path resolution.
- **Podcast service**: `podflow/services/podcast_service.py` — end-to-end pipeline orchestration.
- **Airflow DAG**: `podflow/airflow/podcast_pipeline.py` — scheduled every 6 hours.
- **DAG loader**: `airflow_home/dags/podflow_dag_loader.py` — Airflow discovery entry point.

### Phase 4 — Documentation

**Status:** ✅ Complete (current)

- Architecture document.
- Project structure document.
- Database schema document.
- Domain model document.
- Development guide.
- Roadmap (this document).
- Architecture decision records.

---

## Future Phases

### Phase 5 — Testing

**Status:** 🔜 Planned

- Unit tests for domain objects (`Episode`, `Podcast`, `ProcessingState`, `SourceType`).
- Unit tests for `EpisodeParser` (duration parsing, audio URL extraction, date parsing).
- Unit tests for `FileManager` (filename sanitization, extension detection).
- Integration tests for `PodcastRepository` and `EpisodeRepository` (in-memory SQLite).
- Integration tests for `PodcastService.run()` with mocked HTTP.
- Airflow DAG structure tests.

### Phase 6 — End-to-End Pipeline Run

**Status:** 🔜 Planned

- First real pipeline run against Marketplace RSS feed.
- Verify episode metadata is correctly parsed and stored.
- Verify audio files download successfully.
- Verify idempotency (second run inserts zero new episodes).
- Verify soft-delete filtering.
- Verify state transitions (NEW → DOWNLOADED → FAILED).

### Phase 7 — YouTube Ingestion

**Status:** 📋 Backlog

- `podflow/ingestion/youtube_reader.py` — YouTube Data API or `yt-dlp` integration.
- Youtube channel → `Podcast` domain object with `source_type=YOUTUBE`.
- Youtube video → `Episode` domain objects with audio URL extraction.
- Zero changes to `PodcastService` or database layer (same domain objects).

### Phase 8 — Multi-Stage Airflow DAG

**Status:** 📋 Backlog

- Split single-task DAG into separate Airflow tasks per processing stage.
- Download task: targets `NEW` episodes.
- (Future) Transcribe task: targets `DOWNLOADED` episodes.
- (Future) Summarize task: targets `TRANSCRIBED` episodes.
- Each task independently retryable at Airflow level.

### Phase 9 — Transcription

**Status:** 📋 Backlog

- Speech-to-text integration (Whisper, Deepgram, or cloud API).
- `podflow/services/transcription_service.py`.
- Episode transitions: `DOWNLOADED → TRANSCRIBED` or `DOWNLOADED → FAILED`.

### Phase 10 — AI Summarization

**Status:** 📋 Backlog

- LLM-based episode summarization (OpenAI, Anthropic, or local model).
- `podflow/services/summarization_service.py`.
- Episode transitions: `TRANSCRIBED → SUMMARIZED`.

### Phase 11 — Semantic Search

**Status:** 📋 Backlog

- Text embedding generation for episode transcripts and summaries.
- Vector database or SQLite extension for similarity search.
- Episode transitions: `SUMMARIZED → EMBEDDED → INDEXED → COMPLETE`.

### Phase 12 — FastAPI Backend

**Status:** 📋 Backlog

- REST API for querying podcasts, episodes, and processing states.
- Endpoints for triggering pipeline runs, retrying failed episodes.
- Imports `PodcastService` and repositories directly — no Airflow dependency.

### Phase 13 — Web Frontend

**Status:** 📋 Backlog

- UI for browsing podcasts and episodes.
- Search interface.
- Pipeline health dashboard.
- User authentication.

### Phase 14 — Productionization

**Status:** 📋 Backlog

- PostgreSQL migration (replace SQLite).
- Alembic for schema migrations.
- Docker containerization.
- Cloud deployment (AWS/GCP/Azure).
- Monitoring and alerting.
- CI/CD pipeline.

---

## Technical Debt

| Item | Severity | Plan |
|---|---|---|
| Stub files (`rss.py`, `parser.py`, `youtube.py`) | Low | Remove when YouTube ingestion is implemented; already superseded by `rss_reader.py` and `episode_parser.py` |
| `src/` directory (empty) | Low | Remove in next cleanup pass |
| `requirements.txt` uses `pip freeze` (all deps pinned) | Medium | Migrate to `pyproject.toml` with `[project.dependencies]` |
| No test infrastructure | Medium | Phase 5 |
| No database migration framework | Low | Alembic when PostgreSQL is needed |
| `datetime.utcnow()` is deprecated in Python 3.13+ | Low | Migrate to `datetime.now(datetime.UTC)` |

---

## Milestones

| Milestone | Phase | Target |
|---|---|---|
| Foundation layer built and verified | 2 | ✅ Done |
| Pipeline code written and unit-verified | 3 | ✅ Done |
| Documentation complete | 4 | ✅ In progress |
| Test suite passing | 5 | Next |
| First real pipeline run | 6 | After testing |
| Multi-source ingestion (RSS + YouTube) | 7 | After E2E run |
| Transcription working | 9 | After multi-source |

---

## Future Evolution

This roadmap is a living document. Phases may be reordered based on priorities — for example, the FastAPI backend could be pulled forward if there's a need to query the database before transcription is implemented. The architecture is designed so that layers can be built in any order without blocking each other.
