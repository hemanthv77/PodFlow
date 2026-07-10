# PodFlow Architecture — Version 1

> **Frozen:** 2026-07-10 — Phase 5 completion
> **Status:** Production-ready foundation. 553 episodes ingested, 2 downloaded, 25 tests passing.

## Overview

PodFlow v1 is a podcast ingestion and asset management pipeline. It discovers episodes from RSS feeds, persists metadata to SQLite, downloads audio with integrity checks, and tracks every episode through an 18-state observable processing machine. Apache Airflow, a CLI, and future FastAPI all share the same service layer.

---

## V1 Capabilities

| Capability | Service | Entry Point |
|---|---|---|
| Ingest RSS feed | `PodcastService` | `podflow ingest <url>` |
| Download audio | `DownloadService` | `podflow download --limit N` |
| Full pipeline | `PipelineService` | `podflow pipeline <url>` |
| Orchestrate via Airflow | `podcast_pipeline` DAG | Every 6 hours |
| Structured events | `logging/events.py` | All services emit to logger |
| Integrity verification | SHA-256 + file size | Stored per episode |
| Error categorization | Retryable / Skip / Abort | `AudioDownloader._categorize_error()` |
| Atomic writes | `.part` → rename | `AudioDownloader` |

---

## Layered Architecture

```
                        Airflow / CLI
                             │
                    ┌────────▼────────┐
                    │ PipelineService │  ← single entry point
                    └────┬───────┬────┘
                         │       │
              ┌──────────▼──┐ ┌──▼───────────────┐
              │PodcastService│ │ DownloadService   │
              └──────┬───────┘ └──┬───┬───────────┘
                     │            │   │
        ┌────────────┼────┐       │   │
        ▼            ▼    ▼       ▼   ▼
   RSSFeedReader  FeedParser  AudioDownloader  FileManager
        │            │            │               │
        └────────────┴────────────┴───────────────┘
                            │
                   ┌────────▼────────┐
                   │   Repositories   │
                   │  (Podcast, Ep)   │
                   └────────┬────────┘
                            │
                   ┌────────▼────────┐
                   │     SQLite       │
                   └─────────────────┘

Cross-cutting: config/  logging/  exceptions/  domain/
```

---

## Service Layer

Three services, each owning one business capability:

| Service | Responsibility | Input | Output |
|---|---|---|---|
| `PodcastService` | Fetch RSS, parse, persist | RSS URL | `IngestionResult` |
| `DownloadService` | Download audio for NEW episodes | None (queries DB) | `DownloadStats` |
| `PipelineService` | Orchestrate the full workflow | RSS URL | `PipelineReport` |

Every service supports zero-config usage (`Service()`) and dependency injection for testing (`Service(downloader=mock)`).

---

## Processing State Machine

18 states with per-stage failure isolation:

```
NEW → DISCOVERED → QUEUED → DOWNLOADING → DOWNLOADED
                        ↓                    ↑
                   FAILED_DOWNLOAD           │
                                             │
              TRANSCRIBING → TRANSCRIBED     │ (future)
                   ↓                         │
              FAILED_TRANSCRIPTION           │
                                             │
              SUMMARIZING → SUMMARIZED       │ (future)
                   ↓                         │
              FAILED_SUMMARIZATION           │
                                             │
              EMBEDDING → EMBEDDED           │ (future)
                   ↓                         │
              FAILED_EMBEDDING              │
                                             │
                                       COMPLETE
```

Linear progression enforced by `ProcessingState.transition_to()`. Failure transitions bypass validation.

---

## Workflow Events

Every service action emits a structured key=value log event:

```
event=pipeline.started url=...
event=ingest.fetched url=...
event=ingest.completed podcast=... found=553 new=553 elapsed=4.6
event=download.batch.started episodes=553
event=download.episode.started episode=...
event=download.episode.completed episode=... bytes=... sha256=...
event=download.batch.completed checked=2 downloaded=2 skipped=0 failed=0
event=pipeline.completed podcast=... discovered=553 inserted=553 downloaded=2
```

All events flow through `get_logger("podflow.events")` — parseable by any log aggregator.

---

## Domain Layer

| Object | Purpose |
|---|---|
| `Podcast` | Feed metadata (title, author, source_type) |
| `Episode` | Parsed episode (title, guid, audio_url, duration) |
| `ProcessingState` | 18-state enum with transition validation |
| `SourceType` | RSS, YOUTUBE, SPOTIFY, APPLE_PODCASTS |
| `IngestionResult` | PodcastService output |
| `DownloadResult` | AudioDownloader output |
| `DownloadStats` | DownloadService output |
| `PipelineReport` | Composed workflow receipt |

Domain objects have zero framework dependencies — no SQLAlchemy, no httpx, no Airflow.

---

## Database

SQLite via SQLAlchemy. Two tables:

- **podcasts** (14 columns) — source_type, rss_url (unique), metadata, last_checked_at
- **episodes** (19 columns) — FK to podcasts, processing_state (indexed), integrity fields (file_hash, file_size), soft-delete (is_active)

Repositories: `PodcastRepository`, `EpisodeRepository`. No further repositories — new queries extend existing ones.

---

## Error Handling

Three-tier categorization in `AudioDownloader._categorize_error()`:

| HTTP/OS Condition | Exception | Behaviour |
|---|---|---|
| 404, 410 | `SkipDownloadError` | Fail immediately, no retry |
| 5xx, timeout, connection reset | `RetryableDownloadError` | Retry up to `max_retries` |
| ENOSPC, EACCES | `AbortDownloadError` | Fail immediately, abort batch |

---

## Testing

25 unit tests + 2 integration tests against live Talk Python feed:

```
$ .venv/bin/pytest tests/ -v
25 passed  # FileManager (11), AudioDownloader (8), DownloadService (6)
2 passed   # Integration (fresh pipeline, idempotent re-run)
```

---

## CLI

```
python -m podflow.cli ingest <url>
python -m podflow.cli download --limit 5
python -m podflow.cli pipeline <url> --limit 2
```

Exercises the same services as Airflow and future FastAPI.

---

## Airflow DAG

```
@dag(schedule=timedelta(hours=6))
def podcast_pipeline():
    @task
    def run_pipeline():
        return PipelineService().run(settings.rss_url)
```

3 imports, 1 task, 1 call. Zero business logic.

---

## Configuration

```
DATABASE_PATH=data/podflow.db
DOWNLOAD_DIR=downloads
DOWNLOAD_TIMEOUT=120
DOWNLOAD_MAX_RETRIES=3
RSS_FETCH_TIMEOUT=30
LOG_LEVEL=INFO
```

Loaded via `pydantic-settings` from `.env`. Singleton `settings` imported everywhere.

---

## V1 Line Count

```
podflow/domain/          4 files,  ~350 lines
podflow/ingestion/       2 files,  ~280 lines
podflow/downloader/      2 files,  ~410 lines
podflow/database/        3 files,  ~400 lines
podflow/services/        3 files,  ~550 lines
podflow/config/          1 file,    ~65 lines
podflow/logging/         2 files,   ~80 lines
podflow/exceptions/      1 file,    ~60 lines
podflow/airflow/         1 file,    ~50 lines
podflow/cli.py           1 file,   ~130 lines
tests/                   6 files,  ~650 lines
docs/                    8 files, ~2000 lines
─────────────────────────────────────────
Total:                 34 files, ~5000 lines
```

---

## Stabilization (Phase 6)

| Sprint | Tool | Purpose |
|---|---|---|
| A | `pyproject.toml` | Installable package, `podflow` CLI console script |
| B | Alembic | Versioned schema migrations at `podflow/database/migrations/` |
| C | Docker + docker-compose | 3 services: podflow, postgres, airflow |
| D | Ruff, Black, MyPy, pytest-cov | All configured in `pyproject.toml`, 0 errors |
| E | pre-commit | 9 hooks enforce lint/format/types on every commit |
| F | GitHub Actions CI | Lint, mypy, tests on push/PR to main |
| G | Documentation | DEPLOYMENT, CONTRIBUTING, RELEASE_PROCESS |

### Quality Gates

```
ruff check    → 0 errors
black --check → 44 files unchanged
mypy          → 0 errors in 37 files
pytest        → 27 passed, 0 failed
pre-commit    → 9/9 hooks pass
```

### Database Backend

```bash
DB_BACKEND=sqlite      # default, local dev (zero config)
DB_BACKEND=postgresql  # Docker / production
```

PostgreSQL connection configured in `.env`; `session.py` adapts automatically.

---

## Future Evolution

- **Transcription / Summarization**: Add services, extend state machine — zero schema changes.
- **YouTube ingestion**: Add `youtube_reader.py`, emit same `Episode` domain objects.
- **FastAPI backend**: Import `PipelineService` directly — no Airflow dependency.
- **PostgreSQL**: Swap connection string, add Alembic — repository layer unchanged.
- **Asset table**: Evolve `local_path`/`file_hash`/`file_size` into a separate `assets` table when transcript/thumbnail assets arrive.
