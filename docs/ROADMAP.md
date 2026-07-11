# PodFlow Roadmap

> **Document version:** 2.0 — v0.6.0 release
> **Last updated:** 2026-07-11

## Overview

PodFlow is built in phases, each adding a layer of capability. Phases are designed so that each one produces a working, testable increment — the project is never in a broken state between phases.

The backend architecture is **frozen** as of v0.6.0. Future work adds capabilities (frontend, AI processing, additional content sources) atop the existing foundation rather than restructuring it.

---

## Completed Phases

### Phase 1 — Project Scaffolding ✅

**Tag:** — (pre-release)

- Project directory structure created.
- Apache Airflow 3.2 installed and configured (`LocalExecutor`, simple auth).
- Python virtual environment with all dependencies.
- `.env` configuration file with initial values.
- Module stubs created for all planned packages.

### Phase 2 — Foundation Layer ✅

**Tag:** — (pre-release)

- **Configuration**: `podflow/config/settings.py` — pydantic-settings loading from `.env`.
- **Logging**: `podflow/logging/logger.py` — structured logging with `get_logger()`.
- **Exceptions**: `podflow/exceptions/exceptions.py` — typed hierarchy rooted at `PodFlowError`.
- **Database**: SQLAlchemy ORM models (`Podcast`, `Episode`), session factory, repository layer.
- **Domain**: Pure dataclasses — `Podcast`, `Episode`, `ProcessingState` (18-state enum), `SourceType`.
- **Processing state machine**: Validated transitions with per-stage failure isolation.

### Phase 3 — Ingestion Engine ✅

**Tag:** — (pre-release)

- RSS feed reader (`podflow/ingestion/rss_reader.py`) — fetch via `feedparser`.
- Episode parser (`podflow/ingestion/episode_parser.py`) — raw RSS → domain objects.
- `PodcastService` — fetch → parse → persist orchestration.

### Phase 4 — Asset Management ✅

**Tag:** — (pre-release)

- `FileManager` — type-specific subdirectories, safe filenames, path resolution.
- `AudioDownloader` — HTTP streaming with retry, SHA-256 integrity, atomic writes (`.part → rename`).
- Error categorization: `RetryableDownloadError`, `SkipDownloadError`, `AbortDownloadError`.
- `DownloadService` — batch download with state transitions.

### Phase 5 — Workflow Orchestration ✅

**Tag:** `v0.5.0`

- `PipelineService` — single entry point orchestrating ingest + download.
- Airflow DAG (`podcast_pipeline`) — scheduled every 6 hours, 1 task, 0 business logic.
- CLI (`podflow ingest/download/pipeline`) — same services as Airflow and API.
- Integration tests — real Talk Python feed, idempotency verification.
- **27 tests passing.**

### Phase 6 — Platform API & Production Readiness ✅

**Tag:** `v0.6.0`

- **FastAPI application** with 12 endpoints under `/api/v1/`.
- **Middleware stack**: CORS, Security Headers, GZip, Request ID, Correlation ID, Request Logging.
- **Request tracing**: `X-Request-ID` and `X-Correlation-ID` on every response and log record.
- **Security headers**: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`.
- **RFC 7807 error contract**: `type`, `title`, `status`, `detail`, `instance`, `request_id`, `correlation_id`.
- **API versioning**: Configurable `API_VERSION` → `/api/{version}/` prefix, no hardcoded paths.
- **GZip compression**: Responses ≥ 1 KB compressed (configurable).
- **Graceful shutdown**: Lifespan handler with structured logging and DB engine disposal.
- **Packaging**: `pyproject.toml`, `pip install -e .`, `podflow-api` console script.
- **Alembic migrations**: Versioned schema management.
- **Docker**: `docker-compose.yml` with podflow, postgres, airflow services.
- **Code quality**: Ruff, Black, MyPy (0 errors), pre-commit (9 hooks).
- **CI**: GitHub Actions — lint, mypy, tests on push/PR.
- **Documentation**: 12 docs including ARCHITECTURE_V1, API_REFERENCE, DEPLOYMENT, DIAGRAMS.
- **74 tests passing** (48 unit/integration + 26 production readiness).

---

## Future Phases

> **Architecture note:** All future phases build on the frozen v1 foundation. No restructuring of the backend architecture is planned.

### Phase 7 — Authentication & Rate Limiting

**Status:** 🔜 Planned — recommended before public exposure

- API key or JWT middleware for mutation endpoints (`POST /ingestions`, `/downloads`, `/pipeline-executions`).
- Role-based access: read-only vs. admin.
- Rate limiting per key/IP for ingestion and download endpoints.

### Phase 8 — YouTube Ingestion

**Status:** 📋 Backlog

- `podflow/ingestion/youtube_reader.py` — YouTube Data API or `yt-dlp` integration.
- YouTube channel → `Podcast` domain object with `source_type=YOUTUBE`.
- YouTube video → `Episode` domain objects with audio URL extraction.
- Zero changes to `PodcastService` or database layer — same domain objects, same pipeline.

### Phase 9 — AI Processing Pipeline

**Status:** 📋 Backlog

- **Transcription**: Speech-to-text (Whisper, Deepgram, or cloud API). New `TranscriptionService`.
- **Summarization**: LLM-based episode summaries (OpenAI, Anthropic, or local model). New `SummarizationService`.
- **Embedding**: Text embeddings for semantic search. New `EmbeddingService`.
- State transitions: `DOWNLOADED → TRANSCRIBED → SUMMARIZED → EMBEDDED → COMPLETE`.
- Each stage independently retryable through the existing state machine.

### Phase 10 — Semantic Search API

**Status:** 📋 Backlog

- Vector database integration (pgvector, Chroma, or SQLite extension).
- `GET /api/v1/search?q=...` endpoint — search across transcripts and summaries.
- Relevance-ranked results with episode context.

### Phase 11 — Web Frontend

**Status:** 📋 Backlog

- UI for browsing podcasts and episodes.
- Search interface.
- Pipeline health dashboard.
- User authentication UI.
- Framework TBD (React, htmx, or streamlit).

### Phase 12 — Multi-Stage Airflow DAG

**Status:** 📋 Backlog

- Split single-task DAG into separate Airflow tasks per processing stage.
- Each task independently retryable at Airflow level.
- Task dependencies: ingest → download → transcribe → summarize → embed.

### Phase 13 — Cloud Deployment

**Status:** 📋 Backlog

- Production PostgreSQL (RDS/Cloud SQL).
- Container orchestration (ECS/GKE/Cloud Run).
- Secret management (Vault/Secrets Manager).
- Prometheus metrics + Grafana dashboards.
- Centralized logging (ELK/Loki).
- CD pipeline.

---

## Architecture Freeze

As of v0.6.0, the backend architecture is frozen:

```
FastAPI → Middleware → Routers → DTOs → Services → Repositories → Database
```

- **No business logic** will be added to presentation layers (API, CLI, Airflow).
- **No SQLAlchemy models** will be exposed through the API.
- **Services remain the single source of truth** for business capabilities.
- **Domain objects remain framework-free.**

Changes that *are* allowed:
- New services for new capabilities (e.g., `TranscriptionService`).
- New API endpoints that delegate to services.
- New domain objects for new entity types.
- Backward-compatible schema additions.

---

## Technical Debt

| Item | Severity | Status |
|---|---|---|
| `src/` directory (empty) | Low | Remove in next cleanup |
| `requirements.txt` uses `pip freeze` | Low | Suppressed by `pyproject.toml` |
| `podflow/ingestion/rss.py`, `parser.py`, `youtube.py` (stubs) | Low | Replace when YouTube ingestion is implemented |
| No authentication on mutation endpoints | High | Phase 7 |
| No rate limiting | Medium | Phase 7 |
| Manual `/metrics` endpoint | Low | Replace with prometheus-fastapi-instrumentator |
| B008 ruff warnings (Depends in defaults) | Low | Standard FastAPI pattern — suppress in config |

---

## Milestones

| Milestone | Tag | Date | Tests |
|---|---|---|---|
| Foundation layer built | — | 2026-07-09 | — |
| Ingestion engine complete | — | 2026-07-09 | — |
| Asset management complete | — | 2026-07-10 | — |
| Workflow orchestration | `v0.5.0` | 2026-07-10 | 27 |
| Platform API & Production Readiness | `v0.6.0` | 2026-07-11 | 74 |
| Authentication & Rate Limiting | TBD | TBD | — |
| YouTube ingestion | TBD | TBD | — |
| AI processing pipeline | TBD | TBD | — |
