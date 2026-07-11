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

### API Hardening

- [ ] Set `ENABLE_HTTPS=true` to add `Strict-Transport-Security` header
- [ ] Review `CORS_ORIGINS` — restrict from `*` to specific domains
- [ ] Set `GZIP_MIN_SIZE` — default 1024 (1 KB), adjust for your payloads
- [ ] Configure `API_VERSION` — default `v1`, bump on breaking changes
- [ ] Verify security headers: `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy`
- [ ] Ensure reverse proxy (nginx, Cloudflare) forwards `X-Forwarded-For` for client IP logging
- [ ] Propagate `X-Correlation-ID` across services for distributed tracing

### Database

- [ ] Switch `DB_BACKEND=postgresql`
- [ ] Set strong `DB_PASSWORD`
- [ ] Run `alembic upgrade head` on deploy
- [ ] Set up backup for `data/` (or PostgreSQL dump)

### Airflow

- [ ] Enable Airflow authentication in `airflow.cfg`
- [ ] Configure Airflow `schedule_interval` for production cadence

### Observability

- [ ] Monitor `podflow.events` log stream for pipeline failures
- [ ] Aggregate structured log records (`rid=`, `cid=`) in your log aggregator
- [ ] Alert on `/health` and `/ready` endpoint failures
- [ ] Track `/api/v1/metrics` for podcast/episode counts and uptime

### API Startup

```bash
# Development
podflow-api

# Production (via uvicorn with multiple workers)
uvicorn podflow.api.main:create_app \
  --factory \
  --host 0.0.0.0 \
  --port 8000 \
  --workers 4 \
  --log-level info

# Or via docker compose
docker compose up -d
```

### Request Tracing

Every API response includes:
- `X-Request-ID` — unique per-request UUID v4
- `X-Correlation-ID` — client-supplied or auto-generated UUID for cross-service tracing

All log records emitted during a request include `rid=` and `cid=` fields.

### Error Responses

All errors follow RFC 7807 with fields: `type`, `title`, `status`, `detail`,
`instance`, `request_id`, `correlation_id`.

### Security Headers

| Header | Value | Condition |
|---|---|---|
| `X-Content-Type-Options` | `nosniff` | Always |
| `X-Frame-Options` | `DENY` | Always |
| `Referrer-Policy` | `no-referrer` | Always |
| `Permissions-Policy` | `` (empty) | Always |
| `Strict-Transport-Security` | `max-age=31536000; includeSubDomains` | When `ENABLE_HTTPS=true` |
