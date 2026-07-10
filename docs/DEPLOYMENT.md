# PodFlow — Deployment Guide

> **Version:** 0.5.0

## Local Development

### Prerequisites

- Python 3.12+
- virtualenv or venv

### Setup

```bash
git clone https://github.com/hemanthv77/PodFlow.git
cd PodFlow
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
pip install -r requirements.txt  # optional, installs Airflow
```

### Run

```bash
# Full pipeline (ingest + download 2 episodes)
podflow pipeline https://talkpython.fm/episodes/rss --limit 2

# CLI help
podflow --help

# Tests
pytest tests/ -v

# Quality checks
pre-commit run --all-files
```

---

## Docker

### Start all services

```bash
docker compose up -d
```

This starts:
- `podflow-app` — runs pipeline on startup, then exits
- `postgres` — PostgreSQL 16 with healthcheck
- `airflow` — Airflow webserver (port 8080) + scheduler

### Run pipeline manually

```bash
docker compose run --rm podflow pipeline https://talkpython.fm/episodes/rss --limit 5
```

### View Airflow UI

Open `http://localhost:8080`. Login: `admin` / `admin`.

### Stop

```bash
docker compose down
```

---

## Database Configuration

| Environment | Backend | Config |
|---|---|---|
| **Local dev** | SQLite | `DB_BACKEND=sqlite` (default) |
| **Docker** | PostgreSQL | `DB_BACKEND=postgresql`, `DB_HOST=postgres` |
| **Production** | PostgreSQL | Set `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASSWORD` |

All config via `.env` or environment variables.

---

## Migrations (Alembic)

```bash
# Generate after model change
alembic revision --autogenerate -m "description"

# Apply
alembic upgrade head

# Check status
alembic current
```

---

## Production Checklist

- [ ] Switch `DB_BACKEND=postgresql`
- [ ] Set strong `DB_PASSWORD`
- [ ] Run `alembic upgrade head` on deploy
- [ ] Enable Airflow authentication in `airflow.cfg`
- [ ] Configure Airflow `schedule_interval` for production cadence
- [ ] Set up backup for `data/` (or PostgreSQL dump)
- [ ] Monitor `podflow.events` log stream for pipeline failures
