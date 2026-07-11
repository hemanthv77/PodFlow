# PodFlow API Reference

> **Base URL:** `/api/v1`
> **Version:** 0.5.0
> **Content-Type:** `application/json`

Interactive docs available at `/docs` (Swagger UI) and `/redoc` (ReDoc) when
the API server is running.

---

## Request Tracing

Every response includes:

| Header | Description |
|---|---|
| `X-Request-ID` | Unique UUID v4 per request |
| `X-Correlation-ID` | Client-supplied (or auto-generated) UUID for cross-service tracing |

Send `X-Correlation-ID` in your request to propagate a trace:

```bash
curl -H "X-Correlation-ID: my-trace-123" http://localhost:8000/api/v1/podcasts
```

Both IDs appear in structured log output as `rid=` and `cid=` fields.

---

## Error Contract

All errors follow RFC 7807 *Problem Details*.  Every error response contains:

```json
{
  "type": "https://errors.podflow.dev/not-found",
  "title": "Not Found",
  "status": 404,
  "detail": "The path '/api/v1/podcasts/999' was not found on this server.",
  "instance": "/api/v1/podcasts/999",
  "request_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
  "correlation_id": "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
}
```

| Field | Description |
|---|---|
| `type` | URI identifying the problem category |
| `title` | Short human-readable summary |
| `status` | HTTP status code |
| `detail` | Human-readable explanation |
| `instance` | Request path that triggered the error |
| `request_id` | `X-Request-ID` for this request |
| `correlation_id` | `X-Correlation-ID` for distributed tracing |

### Error Types

| Status | Type URI | When |
|---|---|---|
| 404 | `https://errors.podflow.dev/not-found` | Resource or path not found |
| 405 | `https://errors.podflow.dev/method-not-allowed` | HTTP method not supported |
| 422 | (FastAPI built-in) | Request validation failure |
| 500 | `https://errors.podflow.dev/internal-error` | Unhandled server error |
| 502 | `https://errors.podflow.dev/rssfetcherror` | Upstream RSS feed unreachable |
| 502 | `https://errors.podflow.dev/rssparseerror` | RSS feed parsing failed |
| 502 | `https://errors.podflow.dev/downloaderror` | Audio download failed |
| 507 | `https://errors.podflow.dev/abortdownloaderror` | Disk full or permission error |

---

## Security Headers

All responses include:

| Header | Value |
|---|---|
| `X-Content-Type-Options` | `nosniff` |
| `X-Frame-Options` | `DENY` |
| `Referrer-Policy` | `no-referrer` |
| `Permissions-Policy` | `` (empty — deny all powerful features) |

When `ENABLE_HTTPS=true` (production), `Strict-Transport-Security` is also added.

---

## Pagination

All list endpoints accept:

| Parameter | Type | Default | Range |
|---|---|---|---|
| `offset` | `int` | `0` | ≥ 0 |
| `limit` | `int` | `50` | 1–500 |

Response envelope for list endpoints:

```json
{
  "items": [...],
  "total": 553,
  "offset": 0,
  "limit": 50
}
```

---

## Endpoints

### Platform

#### `GET /health`

Liveness probe.

**Response** `200`
```json
{"status": "ok"}
```

---

#### `GET /ready`

Readiness probe — verifies database connectivity.

**Response** `200`
```json
{"status": "ready", "database": "connected"}
```

---

#### `GET /version`

Application version information.

**Response** `200`
```json
{
  "app": "PodFlow",
  "version": "0.5.0",
  "api_version": "v1",
  "git_sha": "abc1234",
  "python": "3.12"
}
```

---

#### `GET /api/v1/metrics`

Platform operational metrics.

**Response** `200`
```json
{
  "podcasts": 5,
  "episodes": 553,
  "downloaded_episodes": 2,
  "failed_downloads": 0,
  "database_backend": "sqlite",
  "database_size_mb": 2.4,
  "downloads_size_mb": 58.5,
  "uptime_seconds": 3600.0
}
```

---

#### `GET /api/v1/info`

Application identity.

**Response** `200`
```json
{
  "application": "PodFlow",
  "version": "0.5.0",
  "python_version": "3.12.3",
  "platform": "Linux",
  "database_backend": "sqlite",
  "api_version": "v1"
}
```

---

### Podcasts

#### `GET /api/v1/podcasts`

List podcasts (paginated, sorted).

| Query Param | Type | Default | Description |
|---|---|---|---|
| `offset` | `int` | `0` | Items to skip |
| `limit` | `int` | `50` | Items per page (1–500) |
| `sort_by` | `str` | `title` | Column name; prefix with `-` for descending |
| `source_type` | `str` | — | Filter: `RSS`, `YOUTUBE`, `SPOTIFY`, `APPLE_PODCASTS` |

**Response** `200`
```json
{
  "items": [
    {
      "id": 1,
      "source_type": "RSS",
      "title": "Talk Python To Me",
      "description": "Python conversations for passionate developers",
      "link": "https://talkpython.fm",
      "language": "en-us",
      "image_url": "https://cdn.talkpython.fm/img/cover.png",
      "author": "Michael Kennedy",
      "category": "Technology",
      "rss_url": "https://talkpython.fm/episodes/rss",
      "last_checked_at": "2026-07-10T12:00:00",
      "created_at": "2026-07-10T00:00:00"
    }
  ],
  "total": 1,
  "offset": 0,
  "limit": 50
}
```

---

#### `GET /api/v1/podcasts/{podcast_id}`

Get a single podcast.

**Response** `200` — Podcast object (see above)

**Response** `404` — Podcast not found

---

### Episodes

#### `GET /api/v1/episodes`

List episodes (paginated, sorted, filterable).

| Query Param | Type | Default | Description |
|---|---|---|---|
| `offset` | `int` | `0` | Items to skip |
| `limit` | `int` | `50` | Items per page (1–500) |
| `sort_by` | `str` | `-published_at` | Column name; `-` prefix = descending |
| `podcast_id` | `int` | — | Filter by owning podcast |
| `processing_state` | `str` | — | Filter: `DISCOVERED`, `DOWNLOADED`, etc. |

**Response** `200`
```json
{
  "items": [
    {
      "id": 1,
      "podcast_id": 1,
      "title": "#554: Trustworthy AI in Healthcare",
      "description": "Discussion about AI in medical applications.",
      "guid": "126623d8-741e-4b14-bdca-a75ec70774f9",
      "link": "https://talkpython.fm/episodes/show/554",
      "audio_url": "https://example.com/ep554.mp3",
      "published_at": "2026-07-10T05:10:31",
      "duration": 3640,
      "processing_state": "DOWNLOADED",
      "local_path": "/downloads/audio/ep554.mp3",
      "file_size": 58462737,
      "state_updated_at": "2026-07-10T12:01:00",
      "created_at": "2026-07-10T12:00:00"
    }
  ],
  "total": 553,
  "offset": 0,
  "limit": 50
}
```

---

#### `GET /api/v1/episodes/{episode_id}`

Get a single episode.

**Response** `200` — Episode object (see above)

**Response** `404` — Episode not found

---

### Ingestion

#### `POST /api/v1/ingestions`

Ingest an RSS feed.

**Request**
```json
{
  "rss_url": "https://talkpython.fm/episodes/rss"
}
```

**Response** `201`
```json
{
  "podcast": "Talk Python To Me",
  "episodes_found": 553,
  "new_episodes": 10,
  "skipped_episodes": 543,
  "duration_seconds": 4.6,
  "errors": [],
  "success": true
}
```

---

### Downloads

#### `POST /api/v1/downloads`

Download audio for episodes in `DISCOVERED` state.

**Request**
```json
{
  "limit": 5
}
```

`limit` is optional; omit to download all `DISCOVERED` episodes (max 1000).

**Response** `202`
```json
{
  "episodes_checked": 10,
  "episodes_downloaded": 7,
  "episodes_skipped": 2,
  "episodes_failed": 1,
  "total_bytes": 412000000,
  "duration_seconds": 45.2,
  "errors": [],
  "success": true
}
```

---

### Pipeline

#### `POST /api/v1/pipeline-executions`

Run the full pipeline: ingest RSS + download audio.

**Request**
```json
{
  "rss_url": "https://talkpython.fm/episodes/rss",
  "download_limit": 5
}
```

`download_limit` is optional.

**Response** `202`
```json
{
  "podcast": "Talk Python To Me",
  "discovered": 553,
  "inserted": 10,
  "downloaded": 5,
  "skipped": 5,
  "failed": 0,
  "elapsed": 52.3,
  "errors": [],
  "success": true
}
```
