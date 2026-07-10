# PodFlow Project Structure

> **Document version:** 1.0 — Phase 2 completion
> **Last updated:** 2026-07-10

## Overview

PodFlow follows a Python package structure where all application logic lives under `podflow/` and infrastructure configuration (Airflow, environment) lives at the project root. The `src/` directory is a deprecated artifact and contains no active code.

---

## Project Tree

```
PodFlow/
│
├── podflow/                          # Application package (all business logic)
│   ├── __init__.py
│   │
│   ├── airflow/                      # Airflow DAG definitions
│   │   ├── __init__.py
│   │   └── podcast_pipeline.py       # Main ingestion DAG
│   │
│   ├── config/                       # Configuration management
│   │   ├── __init__.py
│   │   └── settings.py               # pydantic-settings, .env loader
│   │
│   ├── database/                     # Persistence layer
│   │   ├── __init__.py
│   │   ├── models.py                 # SQLAlchemy ORM models
│   │   ├── repository.py             # Data access abstractions
│   │   └── session.py                # Engine, session factory, init_db()
│   │
│   ├── domain/                       # Pure domain objects (zero dependencies)
│   │   ├── __init__.py
│   │   ├── episode.py                # Episode + PipelineResult dataclasses
│   │   ├── podcast.py                # Podcast dataclass + SourceType enum
│   │   └── processing_state.py       # Episode lifecycle state machine
│   │
│   ├── downloader/                   # Audio file acquisition
│   │   ├── __init__.py
│   │   ├── audio.py                  # AudioDownloader (HTTP streaming)
│   │   └── filesystem.py             # FileManager (paths, naming, safety)
│   │
│   ├── exceptions/                   # Custom exception hierarchy
│   │   ├── __init__.py
│   │   └── exceptions.py             # PodFlowError base + subclasses
│   │
│   ├── ingestion/                    # Feed reading and content parsing
│   │   ├── __init__.py
│   │   ├── episode_parser.py         # Raw RSS → list[Episode]
│   │   ├── rss_reader.py             # HTTP fetch + feedparser → FeedData
│   │   ├── parser.py                 # [stub — deprecated]
│   │   ├── rss.py                    # [stub — deprecated]
│   │   └── youtube.py                # [stub — future]
│   │
│   ├── logging/                      # Structured logging
│   │   ├── __init__.py
│   │   └── logger.py                 # get_logger() factory
│   │
│   ├── services/                     # Orchestration / business workflows
│   │   ├── __init__.py
│   │   └── podcast_service.py        # PodcastService.run() — main entry point
│   │
│   └── utils/                        # General-purpose helpers
│       ├── __init__.py
│       └── helpers.py                # [stub]
│
├── airflow_home/                     # Airflow runtime directory
│   ├── airflow.cfg                   # Airflow configuration
│   ├── dags/                         # DAG discovery directory
│   │   └── podflow_dag_loader.py     # Imports from podflow.airflow
│   ├── logs/                         # Airflow logs (gitignored)
│   └── plugins/                      # Airflow plugins (empty)
│
├── data/                             # SQLite database (gitignored)
│   └── podflow.db                    # Auto-created by init_db()
│
├── downloads/                        # Downloaded audio files (gitignored)
│
├── docs/                             # Project documentation
│   ├── ARCHITECTURE.md
│   ├── PROJECT_STRUCTURE.md
│   ├── DATABASE.md
│   ├── DOMAIN_MODEL.md
│   ├── DEVELOPMENT_GUIDE.md
│   ├── ROADMAP.md
│   └── DECISIONS.md
│
├── tests/                            # Test suite (stubs — to be implemented)
│   ├── test_database.py
│   ├── test_downloader.py
│   ├── test_parser.py
│   └── test_rss.py
│
├── src/                              # Deprecated — no active code
│
├── .env                              # Environment variables (gitignored)
├── .gitignore                        # Git ignore rules
├── requirements.txt                  # Frozen dependencies
└── README.md                         # Project overview
```

---

## Directory Explanations

### `podflow/` — Application Package

All business logic, domain objects, and infrastructure code. This package is importable without Airflow running and can be used from any Python context (CLI, FastAPI, tests).

### `podflow/airflow/` — DAG Definitions

Contains Airflow DAG files. These files are **not** directly discovered by Airflow — instead, `airflow_home/dags/podflow_dag_loader.py` imports them. This keeps DAG definitions inside the package for version control and IDE support.

**How to add a new DAG:**
1. Create `podflow/airflow/new_dag.py`.
2. Import it from `airflow_home/dags/podflow_dag_loader.py`.

### `podflow/config/` — Configuration

Centralized, typed configuration using `pydantic-settings`. The `Settings` class reads from `.env` and provides computed properties (`database_url`, `download_path`). A module-level `settings` singleton is imported by all other modules.

**Rule:** No module reads environment variables directly. All configuration flows through `settings.py`.

### `podflow/database/` — Persistence

Three files following separation of concerns:

- **`models.py`** — SQLAlchemy ORM model definitions. Only table structure, no queries.
- **`session.py`** — Engine creation, session factory, and `init_db()` for table creation.
- **`repository.py`** — Data access methods. Business logic calls repositories, never raw SQLAlchemy queries.

### `podflow/domain/` — Domain Objects

Pure Python dataclasses and enums with zero framework dependencies. These objects flow through the pipeline — ingestion produces them, downloader consumes them, services orchestrate them.

**Rule:** Domain objects never import from `database/`, `ingestion/`, `downloader/`, or `services/`.

### `podflow/downloader/` — Audio Acquisition

- **`audio.py`** — HTTP streaming download with retry logic. Depends on `FileManager`.
- **`filesystem.py`** — Path resolution, filename sanitization, existence checks. Single responsibility: filesystem concerns.

### `podflow/exceptions/` — Error Types

A typed exception hierarchy rooted at `PodFlowError`. Each subsystem (ingestion, parsing, download, database) has its own exception subclass. This allows callers to catch errors at the appropriate granularity.

### `podflow/ingestion/` — Feed Acquisition

- **`rss_reader.py`** — Fetches RSS XML via HTTP, parses with `feedparser`, returns a `FeedData` value object containing podcast metadata and raw entries.
- **`episode_parser.py`** — Converts raw feedparser entries into validated `Episode` domain objects. Handles duration parsing, audio URL extraction, and date normalization.

**Stub files:** `rss.py`, `parser.py`, `youtube.py` — empty placeholder files from Phase 1 scaffolding. They are not imported and exist only as markers for future work.

### `podflow/logging/` — Logging

A thin wrapper around Python's `logging` module. `get_logger(name)` returns a pre-configured logger with a consistent format: `timestamp | LEVEL | module | message`. Prevents duplicate handlers on repeated calls.

### `podflow/services/` — Orchestration

The service layer wires collaborators together. `PodcastService` receives all dependencies via constructor injection and sequences the pipeline: fetch → parse → persist → download.

**Rule:** Services contain **orchestration**, not business logic. Business logic lives in the individual components they wire together.

### `podflow/utils/` — Utilities

Reserved for general-purpose helper functions. Currently empty (stub). Anything module-specific should live in its own module, not here.

---

## How to Add a New Module

1. **Does it fit an existing package?** Add the file there.
2. **Is it a new domain concept?** Add to `domain/`.
3. **Is it a new ingestion source?** Add to `ingestion/` (e.g., `youtube_reader.py`). It must emit `domain.Episode` objects.
4. **Is it a new workflow?** Add to `services/`. It should receive dependencies via constructor injection.
5. **Does it need a new package?** Only if it represents a genuinely new architectural concern (e.g., `transcription/`, `summarization/`). Discuss before creating.

---

## Future Evolution

- `src/` will be removed once all code has migrated to `podflow/`.
- Stub files (`rss.py`, `parser.py`, `youtube.py`) will be cleaned up when their replacements are complete.
- `podflow/ingestion/` will grow with `youtube_reader.py`, `spotify_reader.py`, etc.
- `podflow/services/` will grow with `transcription_service.py`, `summarization_service.py`, etc.
- `podflow/utils/` should remain small — if it grows large, the helpers likely belong in more specific modules.
