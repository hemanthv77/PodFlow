# Contributing to PodFlow

## Getting Started

```bash
git clone https://github.com/hemanthv77/PodFlow.git
cd PodFlow
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
pre-commit install
```

## Development Workflow

1. Create a branch: `feature/description` or `fix/description`.
2. Write code following existing patterns.
3. Verify quality gates pass:

```bash
pre-commit run --all-files
pytest tests/ -v
```

4. Commit and push. CI runs on push/PR.

## Architecture Rules

- **Domain layer** (`podflow/domain/`) depends on nothing.
- **Services** receive dependencies via constructor injection, support zero-config defaults, and own no persistence logic.
- **Airflow** is an orchestrator only — no business logic in DAGs.
- **Repositories** are limited to `PodcastRepository` and `EpisodeRepository`. New queries extend existing repositories.

See `docs/ARCHITECTURE_V1.md` for full architectural reference.

## Code Standards

- Type hints on all public methods.
- Google-style docstrings.
- `pathlib.Path` over `os.path`.
- Configuration via `podflow.config.settings`, never hardcoded.
- `logging` via `get_logger(__name__)`, never `print()`.
- Exceptions via `podflow.exceptions` hierarchy.

## Adding a New Feature

1. Does it fit an existing module? Add there.
2. New ingestion source? Add to `podflow/ingestion/` — emit same `Episode` domain objects.
3. New workflow? Add service to `podflow/services/` — use dependency injection.
4. New domain concept? Add to `podflow/domain/` — zero dependencies.
5. New table/column? Add to `podflow/database/models.py`, run `alembic revision --autogenerate`.

## Adding a Migration

```bash
# 1. Edit models.py
# 2. Generate
alembic revision --autogenerate -m "add_column_x"
# 3. Review the generated migration
# 4. Test
alembic upgrade head
pytest tests/ -v
```

## Testing

```bash
pytest tests/ -v                    # all tests
pytest tests/test_downloader.py -v  # specific module
pytest tests/ --cov=podflow         # with coverage
```

27 tests passing. Add tests for new features.

## Questions

Open an issue or discussion on GitHub.
