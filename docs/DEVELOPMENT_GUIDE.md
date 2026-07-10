# PodFlow Development Guide

> **Document version:** 1.0 — Phase 2 completion
> **Last updated:** 2026-07-10

## Overview

This document describes the engineering standards, conventions, and philosophy used in PodFlow. It is prescriptive — code that deviates from these guidelines should have a documented reason.

---

## Development Philosophy

### Architecture First, Implementation Second

Every feature follows this workflow:

1. **Design** — What layers are affected? What new domain concepts exist? What dependencies are needed?
2. **Discuss trade-offs** — Are there simpler alternatives? Does this break existing abstractions?
3. **Implement** — Write the code following the standards below.
4. **Review** — Does it follow the layered architecture? Are dependencies flowing the right direction?
5. **Refactor** — Fix violations before committing.
6. **Commit** — Atomic, well-described commits.

### Principles

- **Single responsibility**: Every module, class, and function does exactly one thing.
- **Dependency inversion**: High-level modules (services) depend on abstractions, not concrete implementations. Dependencies are injected via constructors.
- **Separation of concerns**: Ingestion doesn't know about persistence. Downloading doesn't know about RSS parsing. Airflow doesn't know business logic.
- **Configuration over hardcoding**: No magic numbers, no hardcoded URLs, no inline credentials. Everything configurable comes from `settings.py`.
- **Composition over inheritance**: Use constructor injection and interface-like protocols, not deep class hierarchies.

---

## Coding Standards

### Python Version

Python 3.12+. Use modern language features (`str | None` over `Optional[str]`, `list[dict]` over `List[Dict]`, etc.).

### Type Hints

**Every function, method, and module-level variable must have type annotations.** No exceptions.

```python
# ✅ Correct
def fetch(self, url: str) -> FeedData:
    ...

episodes: list[Episode] = []
```

```python
# ❌ Incorrect
def fetch(self, url):
    ...
```

### Docstrings

Every public class, method, and function must have a docstring. Use Google-style format:

```python
def bulk_upsert(self, podcast_id: int, episodes_data: list[dict]) -> int:
    """Insert new episodes for a podcast, skipping those whose GUID already exists.

    Args:
        podcast_id: The owning podcast's primary key.
        episodes_data: List of dicts with keys matching ``Episode`` columns.

    Returns:
        The number of *new* episodes inserted.
    """
```

### Imports

Organized in three blocks, separated by a blank line:

1. Standard library
2. Third-party packages
3. PodFlow internal modules

```python
from datetime import datetime
from pathlib import Path

from sqlalchemy import Column, Integer

from podflow.config.settings import settings
from podflow.domain.episode import Episode
```

### Variable Naming

- **Classes**: `PascalCase` — `PodcastService`, `RSSFeedReader`
- **Functions/Methods**: `snake_case` — `get_or_create()`, `parse_many()`
- **Variables**: `snake_case` — `rss_url`, `episodes_data`
- **Constants**: `UPPER_SNAKE_CASE` — `_CHUNK_SIZE`, `_UNSAFE_CHARS`
- **Private members**: Prefixed with `_` — `self._session`, `self._timeout`
- **Boolean names**: `is_active`, `has_audio`, `can_transition_to`

### Paths

Always use `pathlib.Path`, never `os.path`:

```python
# ✅ Correct
from pathlib import Path
db_path = Path("data/podflow.db")
db_path.parent.mkdir(parents=True, exist_ok=True)

# ❌ Incorrect
import os
os.makedirs("data", exist_ok=True)
```

---

## Dependency Injection

All external dependencies are passed via constructors. No class creates its own dependencies with `new` (or Python equivalents like direct instantiation of collaborators).

```python
# ✅ Correct — dependencies injected
class PodcastService:
    def __init__(
        self,
        *,
        rss_reader: RSSFeedReader,
        episode_parser: EpisodeParser,
        audio_downloader: AudioDownloader,
        podcast_repo: PodcastRepository,
        episode_repo: EpisodeRepository,
    ) -> None: ...

# ❌ Incorrect — service creates its own dependencies
class PodcastService:
    def __init__(self):
        self._rss_reader = RSSFeedReader()
        self._parser = EpisodeParser()
```

The **composition root** (Airflow DAG, CLI entry point, FastAPI route) is responsible for wiring dependencies together. The service layer receives already-wired objects.

---

## Logging

Use `podflow.logging.logger.get_logger(__name__)` in every module:

```python
from podflow.logging.logger import get_logger

logger = get_logger(__name__)
```

**Never use `print()`.** Log levels:

| Level | Usage |
|---|---|
| `DEBUG` | Detailed diagnostic info (e.g., unrecognized date format) |
| `INFO` | Significant pipeline events (e.g., "Downloaded 5 episodes") |
| `WARNING` | Recoverable issues (e.g., skipping a malformed entry) |
| `ERROR` | Failures that don't abort the pipeline (e.g., one episode download failed) |
| `EXCEPTION` | Unexpected errors caught at boundaries (use `logger.exception()`) |

Log format: `2026-07-10 12:00:00 | INFO     | podflow.services.podcast_service | Pipeline complete`

---

## Error Handling

### Exception Hierarchy

All PodFlow-specific exceptions inherit from `PodFlowError`:

```
PodFlowError
├── IngestionError → RSSFetchError, RSSParseError
├── ParseError → MissingFieldError, InvalidDataError
├── DownloadError
├── FilesystemError
└── DatabaseError
```

### When to Raise

- **Raise domain exceptions** (`RSSFetchError`, `MissingFieldError`) at the boundary where the error occurs.
- **Catch and convert** external exceptions (e.g., `httpx.RequestError` → `DownloadError`).
- **Log and continue** for batch operations where one failure shouldn't abort the batch (e.g., episode parsing skips bad entries, download skips failed files).
- **Let it propagate** for unrecoverable errors — the caller (Airflow DAG) handles top-level exceptions.

### Error Messages in State

When an episode transitions to `FAILED`, store the error message in `episode.error_message`:

```python
self._episode_repo.update_state(
    db_episode.id,
    ProcessingState.FAILED,
    error_message=str(exc),
)
```

---

## Testing Philosophy

### Current State

Test files exist as stubs (`tests/test_database.py`, etc.). They are empty. Test infrastructure is a future phase.

### Planned Approach

1. **Unit tests** for domain objects, parsers, and utilities — no database, no network.
2. **Integration tests** for repositories against an in-memory SQLite database.
3. **Contract tests** for ingestion readers against recorded RSS XML fixtures.
4. **End-to-end tests** for `PodcastService.run()` with mocked HTTP responses.
5. **Airflow DAG tests** verifying DAG structure (task count, dependencies) without executing.

### Principles

- Tests import from `podflow/`, never from `airflow_home/`.
- Repository tests use a separate in-memory SQLite database.
- Network calls are always mocked in tests.
- Domain objects are tested without any framework setup.

---

## Git Workflow

### Branching

- `main` — stable, deployable.
- Feature branches: `feature/descriptive-name`.
- Bug fixes: `fix/descriptive-name`.
- No direct commits to `main`.

### Commits

- Atomic — one logical change per commit.
- Descriptive — "Add ProcessingState enum with transition validation", not "update code".
- No code that doesn't compile or fails smoke tests.

### What Not to Commit

- `.env` (contains secrets or local paths)
- `data/podflow.db` (generated)
- `downloads/` (generated)
- `airflow_home/logs/` (generated)
- `.venv/` (virtual environment)
- `__pycache__/` (compiled Python)

All of these are in `.gitignore`.

---

## Future Evolution

- **Pre-commit hooks**: `ruff` for linting, `mypy` for type checking, `black` for formatting.
- **CI/CD**: GitHub Actions running tests on push, verifying DAG imports.
- **Test coverage**: Target 80%+ line coverage for `podflow/`.
- **Conventional commits**: `feat:`, `fix:`, `docs:`, `refactor:` prefixes for automated changelog generation.
- **Dependency management**: Migrate from `pip freeze` to `pyproject.toml` with version ranges.
