# Architecture Decision Records

> **Document version:** 1.0 — Phase 2 completion
> **Last updated:** 2026-07-10

## Overview

This document records significant architectural decisions made during PodFlow's development. Each entry follows a lightweight ADR (Architecture Decision Record) format: Context, Decision, Alternatives Considered, Why This Was Selected, and Future Implications.

---

## ADR-001: Separate Domain Layer from ORM Models

**Date:** 2026-07-09
**Status:** Accepted

### Context

The system needs to represent podcasts and episodes in two contexts: (1) in-memory during pipeline execution (discovery, parsing, downloading) and (2) persisted in a database for long-term storage. These contexts have different requirements — the pipeline code should not know about database IDs or state columns, and the database should not be coupled to RSS-specific formats.

### Decision

Maintain two parallel type hierarchies:

- **Domain objects** (`domain/podcast.py`, `domain/episode.py`) — pure Python dataclasses with zero framework dependencies.
- **ORM models** (`database/models.py`) — SQLAlchemy mapped classes with persistence concerns.

A repository layer maps between them.

### Alternatives Considered

1. **Single set of SQLAlchemy models used everywhere**: Simpler initially, but couples pipeline logic to the database schema. Changing a column name means changing ingestion code. Harder to test without a database.
2. **TypedDict or Protocol-based interfaces**: Less explicit than dataclasses, no runtime validation, harder to document.
3. **Pydantic models for both**: Adds a heavy dependency to the domain layer, which should have zero dependencies.

### Why This Was Selected

- The domain layer can be tested without any database setup.
- Ingestion sources (RSS, YouTube, Spotify) emit the same `Episode` dataclass — the repository handles mapping regardless of source.
- Database schema changes don't force changes to pipeline logic.
- Follows the Dependency Inversion Principle: high-level modules (services) depend on abstractions (domain objects), not low-level modules (ORM models).

### Future Implications

- Adding a new ingestion source (YouTube) requires zero changes to the database or service layers — it just needs to produce `Episode` domain objects.
- Switching from SQLite to PostgreSQL only changes the engine connection string — the domain layer is unaffected.
- If a separate read model is needed (e.g., for API responses), a third set of DTOs can be added without touching domain or ORM objects.

---

## ADR-002: Airflow as Orchestrator Only

**Date:** 2026-07-09
**Status:** Accepted

### Context

PodFlow uses Apache Airflow, but Airflow DAGs can easily become bloated with business logic — parsing code, database queries, download logic all embedded in `@task` functions. This makes the pipeline untestable outside Airflow and couples the application to a specific orchestrator.

### Decision

**Airflow contains zero business logic.** DAGs are thin wrappers that:

1. Instantiate services with dependencies wired from `settings`.
2. Call a single method (e.g., `PodcastService.run()`).
3. Handle commit/rollback at the DAG level.

All business logic lives in the `podflow` package, which is importable without Airflow.

### Alternatives Considered

1. **Business logic in DAGs**: Common pattern in Airflow projects. Faster to prototype but creates untestable, tightly-coupled code that cannot be reused outside Airflow.
2. **Airflow as a library**: Import Airflow operators inside `podflow/`. Still couples the package to Airflow internals.

### Why This Was Selected

- `podflow` can be used from a CLI, FastAPI, or test harness without Airflow running.
- DAGs can be changed or replaced (e.g., switching to Prefect, Dagster, or a custom scheduler) without rewriting business logic.
- Testing the pipeline does not require an Airflow environment.
- Follows the Single Responsibility Principle: Airflow owns scheduling; `podflow` owns podcast logic.

### Future Implications

- Multiple DAGs can reuse the same `PodcastService` with different schedules or parameters.
- A FastAPI endpoint can trigger `PodcastService.run()` on-demand for ad-hoc ingestion.
- Switching orchestrators (e.g., to Prefect for better observability) is a DAG rewrite, not a business logic rewrite.

---

## ADR-003: Processing State Machine Instead of Boolean Flags

**Date:** 2026-07-10
**Status:** Accepted

### Context

Early designs used a `downloaded` boolean on the Episode model. As the roadmap expanded to include transcription, summarization, embedding, and indexing, it became clear that a single boolean was insufficient — it couldn't represent partial progress, couldn't differentiate between "downloaded but not transcribed" and "fully processed," and couldn't support selective retries.

### Decision

Replace `downloaded: bool` with a `processing_state` column backed by a `ProcessingState` enum with 8 ordered states. The enum enforces valid transitions (e.g., `NEW → DOWNLOADED` is valid, `NEW → INDEXED` is not). `FAILED` is always a valid target. Terminal states (`COMPLETE`, `FAILED`) reject further transitions.

### Alternatives Considered

1. **Multiple boolean flags** (`is_downloaded`, `is_transcribed`, `is_summarized`): No transition enforcement, no ordering, hard to query "what stage is this episode at?"
2. **Separate status tables per stage**: Normalized but overly complex — each stage would need its own table, join queries become expensive, and state is spread across tables.
3. **Integer stage counter**: Simpler than an enum but loses semantic meaning — what does `stage=3` mean? Requires constant lookup.

### Why This Was Selected

- Single column to query, index, and group by.
- Transition validation prevents impossible states (e.g., "summarized but never transcribed").
- Airflow tasks can independently target specific states: `WHERE processing_state = 'DOWNLOADED'`.
- `FAILED` state captures errors without losing partial progress.
- `FAILED` is always reachable — a transcription failure doesn't prevent re-downloading.

### Future Implications

- Adding a new stage (e.g., `REVIEWED` for human QA) is a one-line enum addition.
- A recovery DAG can reset `FAILED → NEW` by bypassing the transition validation (for manual retries).
- The state machine enables a dashboard showing episodes per stage for pipeline health monitoring.

---

## ADR-004: SQLite for Development, PostgreSQL for Production

**Date:** 2026-07-09
**Status:** Accepted

### Context

The project needed a database immediately for storing podcast and episode metadata. Options ranged from embedded databases (SQLite) to full RDBMS (PostgreSQL, MySQL).

### Decision

Use SQLite during development and early phases. Migrate to PostgreSQL when multi-user or production deployment is needed. All database access goes through SQLAlchemy ORM, so the migration is a connection string change plus Alembic for schema management.

### Alternatives Considered

1. **PostgreSQL from day one**: More production-ready but requires Docker, persistent volumes, and connection management — overhead with no benefit at this stage.
2. **DuckDB**: Better for analytical queries but less mature ORM support and ecosystem.

### Why This Was Selected

- Zero setup — no server process, no Docker, no port configuration.
- Single file — easy to backup, reset, or share.
- `check_same_thread=False` handles SQLite's concurrency limitations for Airflow's single-threaded task execution.
- SQLAlchemy abstracts the differences — no SQLite-specific SQL in the codebase.
- Fast iteration — delete `podflow.db` and `init_db()` recreates everything.

### Future Implications

- `check_same_thread=False` is the only SQLite-specific code; it will be removed on PostgreSQL migration.
- Alembic will be introduced for versioned migrations before the PostgreSQL switch.
- The repository layer will not change — it already uses SQLAlchemy queries, not raw SQL.

---

## ADR-005: Repository Pattern with Minimal Repository Count

**Date:** 2026-07-10
**Status:** Accepted

### Context

Many projects create a repository per database table, leading to repository proliferation: `PodcastRepository`, `EpisodeRepository`, `DownloadRepository`, `TranscriptRepository`, etc. This fragments data access logic and creates anemic repositories that do little more than wrap `session.query()`.

### Decision

Maintain exactly two repositories: `PodcastRepository` and `EpisodeRepository`. Workflow-specific queries (e.g., "find episodes ready for transcription") are composed from existing repository methods. New processing stages add methods to existing repositories, not new repository classes.

### Alternatives Considered

1. **Repository per table**: Standard in many codebases. Leads to 10+ repository classes, many with only 1-2 methods.
2. **Generic repository base class**: `BaseRepository[T]` with `get_by_id`, `list_all`, etc. Reduces boilerplate but encourages leaky abstractions.
3. **No repository — raw SQLAlchemy in services**: Simplest but couples services to ORM, making database changes hard.

### Why This Was Selected

- Two repositories are easy to understand and navigate.
- Each method has a clear purpose — no generic `filter()` that leaks SQLAlchemy internals.
- New stages (transcription, summarization) add methods to `EpisodeRepository` — the data is on the same row, so it belongs in the same repository.
- Services orchestrate workflows; repositories persist data. They don't overlap.

### Future Implications

- If a new aggregate root emerges (e.g., `User` for authentication), it gets its own repository.
- If `EpisodeRepository` grows beyond ~10 methods, it should be split — but only when the number of methods justifies it, not preemptively.

---

## ADR-006: httpx over requests

**Date:** 2026-07-10
**Status:** Accepted

### Context

The `AudioDownloader` needs to fetch audio files over HTTP. `requests` is the most popular Python HTTP library, but `httpx` offers better streaming, connection pooling, and async support.

### Decision

Use `httpx` for all HTTP operations (audio downloading, and future RSS fetching upgrades). The `httpx.Client` with `stream()` provides efficient chunked downloads with timeout support.

### Alternatives Considered

1. **`requests`**: More familiar, larger ecosystem. Lacks native async support and has a less efficient streaming API.
2. **`aiohttp`**: Fully async but requires an async runtime. Premature for current synchronous pipeline.
3. **`urllib`**: Standard library but low-level — would require writing retry logic, timeout handling, and streaming from scratch.

### Why This Was Selected

- `httpx` is already in `requirements.txt` (used by Airflow's internal FastAPI server).
- `httpx.stream()` provides clean, efficient chunked downloads.
- `httpx.Client` supports connection pooling, reducing overhead for multiple downloads.
- Future async migration is easier — switch `Client` to `AsyncClient` without changing the API shape.

### Future Implications

- If the pipeline becomes async, `AsyncClient` can replace `Client` with minimal changes.
- Connection pooling will be important when downloading hundreds of episodes in a batch.
- `httpx`'s retry middleware could replace the current manual retry loop in `AudioDownloader`.

---

## ADR-007: Composition Root in the Airflow DAG

**Date:** 2026-07-10
**Status:** Accepted

### Context

`PodcastService` requires 5 dependencies. Those dependencies themselves require dependencies (`FileManager` needs a `Path`, `RSSFeedReader` needs a timeout). Somewhere in the system, all these objects must be instantiated and wired together.

### Decision

The Airflow DAG is the **composition root** — it creates all objects and wires them. The DAG:

1. Reads configuration from `settings`.
2. Creates concrete instances of all collaborators.
3. Passes them to `PodcastService`.
4. Manages the database session lifecycle (create, commit, rollback, close).

### Alternatives Considered

1. **Dependency injection framework** (e.g., `dependency-injector`): Adds a dependency, learning curve, and indirection. Overkill for a project with ~5 services.
2. **Factory functions in each module**: Each module provides a `create_*()` factory. Spreads wiring logic across the codebase instead of centralizing it.
3. **Service locator pattern**: A global registry of services. Hides dependencies, makes testing harder.

### Why This Was Selected

- Single place to understand how the system is wired.
- Easy to swap implementations (e.g., mock `RSSFeedReader` for testing by passing a different instance).
- No framework magic — plain Python constructor calls.
- The composition root can live anywhere — a CLI command, a FastAPI route, or a test fixture can all wire the same service differently.

### Future Implications

- When a FastAPI backend is added, its route handlers become alternative composition roots.
- If dependency count grows (10+ collaborators), a lightweight DI container may be warranted. Re-evaluate at that point.
- The composition root pattern makes it obvious when the dependency graph is too complex — if the DAG needs 20 lines of constructor calls, it's a signal to simplify.

---

## Future Evolution

New ADRs will be added as significant decisions are made. Each ADR is immutable once accepted — if a decision is reversed, a new ADR is written that supersedes the old one, with a reference to the original.
