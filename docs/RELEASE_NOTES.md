# PodFlow v0.6.0 — FastAPI Platform & Production Readiness

> **Released:** 2026-07-11
> **Tag:** `v0.6.0`
> **Previous:** `v0.5.0`

---

## Summary

v0.6.0 is a **major milestone**: the PodFlow backend is now a production-grade
REST API platform. Every capability from v0.5.0 — RSS ingestion, audio download,
pipeline orchestration — is now accessible through a versioned, documented,
secured, and observable HTTP API. The architecture is frozen; future releases
will add capabilities atop this foundation.

---

## New in v0.6.0

### FastAPI Platform

- **12 endpoints** under `/api/v1/` covering ingestion, downloads, pipeline
  execution, podcast/episode queries, metrics, and platform health.
- **3 read-only query endpoints** with pagination, sorting, and filtering:
  `GET /podcasts`, `GET /episodes`, `GET /episodes/{id}`.
- **3 mutation endpoints**: `POST /ingestions`, `POST /downloads`,
  `POST /pipeline-executions`.
- **3 platform endpoints**: `/health`, `/ready`, `/version`.
- Interactive docs at `/docs` (Swagger) and `/redoc` (ReDoc).

### Middleware Stack

| Middleware | Purpose |
|---|---|
| CORS | Cross-origin access control (configurable origins) |
| Security Headers | `X-Content-Type-Options`, `X-Frame-Options`, `Referrer-Policy`, `Permissions-Policy` |
| GZip | Compress responses ≥ 1 KB (configurable `GZIP_MIN_SIZE`) |
| Request ID | UUID v4 `X-Request-ID` per request |
| Correlation ID | Accept/propagate `X-Correlation-ID` for distributed tracing |
| Request Logging | Structured log: method, path, status, duration, client IP |

### Request Tracing

Every API response and log record now includes:
- `X-Request-ID` — unique per-request UUID
- `X-Correlation-ID` — client-supplied or auto-generated for cross-service tracing

Both IDs appear in structured log output as `rid=` and `cid=` fields.

### Security Hardening

- **4 baseline security headers** on every response.
- **Strict-Transport-Security** when `ENABLE_HTTPS=true` (production).
- **RFC 7807 error contract** — all errors return `type`, `title`, `status`,
  `detail`, `instance`, `request_id`, `correlation_id`.
- No authentication yet — planned for v0.7.0.

### API Versioning

- Configurable `API_VERSION` setting (default `v1`).
- All versioned routes under `/api/{API_VERSION}/`.
- No hardcoded paths — bump `API_VERSION` to `v2` to version the entire surface.

### Graceful Shutdown

- Lifespan handler with structured startup/shutdown logging.
- SQLAlchemy engine disposed cleanly on shutdown.
- Active requests drained before process exit.

### Production Readiness Testing

- **26 new tests** covering request IDs, correlation IDs, security headers,
  GZip, RFC 7807 error contract, startup, shutdown, and tracing on all endpoints.
- **74 total tests** (48 unit/integration + 26 production readiness).

### Packaging & Tooling

- `pyproject.toml` with `podflow-api` console script.
- Alembic for versioned schema migrations.
- Docker + docker-compose (podflow, postgres, airflow).
- Ruff, Black, MyPy (0 errors), pre-commit (9 hooks).
- GitHub Actions CI (lint, mypy, tests).

---

## Architecture Freeze

As of v0.6.0, the backend architecture is frozen:

```
FastAPI → Middleware → Routers → DTOs → Services → Repositories → Database
```

**Rules going forward:**
- No business logic in presentation layers (API, CLI, Airflow).
- No SQLAlchemy models exposed through the API.
- Services remain the single source of truth.
- Domain objects remain framework-free.

---

## Upgrade Guide

### From v0.5.0

1. Pull the tag: `git checkout v0.6.0`
2. Reinstall package: `pip install -e .`
3. Run migrations: `alembic upgrade head`
4. Start API: `podflow-api` or `uvicorn podflow.api.main:create_app --factory`

### New environment variables

| Variable | Default | Purpose |
|---|---|---|
| `API_VERSION` | `v1` | URL prefix segment |
| `ENABLE_HTTPS` | `false` | Enables HSTS header |
| `GZIP_MIN_SIZE` | `1024` | Min response bytes for GZip |

Backward compatible — all new settings have sensible defaults.

---

## Breaking Changes

- **Error response shape changed**: Previously `{"detail": "...", "error_type": "..."}`.
  Now RFC 7807: `{"type": "...", "title": "...", "status": ..., "detail": "...",
  "instance": "...", "request_id": "...", "correlation_id": "..."}`.
- **Negative podcast ID test**: `GET /api/v1/podcasts/-1` now returns 404 instead
  of 422 (negative IDs are valid ints — route matches, query returns nothing).

---

## Known Gaps

| Gap | Severity | Plan |
|---|---|---|
| No authentication on mutation endpoints | High | v0.7.0 |
| No rate limiting | Medium | v0.7.0 |
| Pipeline runs are synchronous | Medium | Move to background tasks |
| Manual `/metrics` endpoint | Low | Replace with Prometheus instrumentation |
| No Content-Security-Policy header | Low | Add after frontend deployment |

---

## Stats

| Metric | v0.5.0 | v0.6.0 |
|---|---|---|
| Test count | 27 | **74** |
| API endpoints | 0 | **12** |
| Middleware | 1 (CORS) | **6** |
| Error response fields | 2 | **7** (RFC 7807) |
| Docs pages | 8 | **13** |

---

## Contributors

Built by [@hemanthv77](https://github.com/hemanthv77).
