# PodFlow UML Diagrams — Version 1

> **Generated:** 2026-07-10
> **Source:** Mermaid (render in any Mermaid-compatible viewer)

---

## 1. Class Diagram — Domain & Services

```mermaid
classDiagram
    direction TB

    %% ── Domain ──
    class Podcast {
        +str rss_url
        +str title
        +SourceType source_type
        +str description
        +str link
        +str language
        +str image_url
        +str author
        +str category
    }

    class Episode {
        +str title
        +str guid
        +str audio_url
        +str description
        +str link
        +datetime published_at
        +int duration
    }

    class ProcessingState {
        <<enumeration>>
        NEW
        DISCOVERED
        QUEUED
        DOWNLOADING
        DOWNLOADED
        FAILED_DOWNLOAD
        TRANSCRIBING
        TRANSCRIBED
        FAILED_TRANSCRIPTION
        SUMMARIZING
        SUMMARIZED
        FAILED_SUMMARIZATION
        EMBEDDING
        EMBEDDED
        FAILED_EMBEDDING
        COMPLETE
        +can_transition_to(target) bool
        +transition_to(target) ProcessingState
        +is_terminal() bool
    }

    class SourceType {
        <<enumeration>>
        RSS
        YOUTUBE
        SPOTIFY
        APPLE_PODCASTS
    }

    class IngestionResult {
        +str podcast
        +int episodes_found
        +int new_episodes
        +int skipped_episodes
        +float duration_seconds
        +list errors
        +success() bool
    }

    class PipelineReport {
        +IngestionResult ingestion
        +DownloadStats download
        +float total_duration
        +list errors
        +podcast() str
        +discovered() int
        +inserted() int
        +downloaded() int
        +skipped() int
        +failed() int
        +success() bool
    }

    class DownloadResult {
        +bool success
        +int bytes_downloaded
        +str sha256
        +float duration_seconds
        +Path destination
    }

    class DownloadStats {
        +int episodes_checked
        +int episodes_downloaded
        +int episodes_skipped
        +int episodes_failed
        +int total_bytes
        +float duration_seconds
        +list errors
        +success() bool
    }

    %% ── Services ──
    class PodcastService {
        -RSSFeedReader _rss_reader
        -FeedParser _parser
        +run(url) IngestionResult
    }

    class DownloadService {
        -AudioDownloader _downloader
        -FileManager _fm
        -EpisodeRepository _episode_repo
        +download_new_episodes(limit) DownloadStats
    }

    class PipelineService {
        -PodcastService _ingest
        -DownloadService _download
        +run(url, limit) PipelineReport
    }

    %% ── Ingestion ──
    class RSSFeedReader {
        -int _timeout
        +fetch(url) dict
    }

    class FeedParser {
        +parse(raw_feed) tuple
        -_parse_podcast(feed) Podcast
        -_parse_episodes(entries) list
    }

    %% ── Downloader ──
    class AudioDownloader {
        -int _timeout
        -int _max_retries
        +download(url, dest) DownloadResult
        -_stream_with_hash(url, dest) tuple
        -_categorize_error(exc) DownloadError
    }

    class FileManager {
        -Path _root
        +ensure_directories()
        +audio_path(ep) Path
        +temporary_path(ep) Path
        +exists(path) bool
    }

    %% ── Repository ──
    class PodcastRepository {
        -Session _session
        +get_or_create(url, type) Podcast
    }

    class EpisodeRepository {
        -Session _session
        +bulk_upsert(id, data) int
        +list_by_state(state) list
        +update_state(id, state) Episode
        +soft_delete(id) Episode
    }

    %% ── Relationships ──
    PipelineService --> PodcastService
    PipelineService --> DownloadService
    PodcastService --> RSSFeedReader
    PodcastService --> FeedParser
    DownloadService --> AudioDownloader
    DownloadService --> FileManager
    DownloadService --> EpisodeRepository
    PodcastService --> PodcastRepository
    PodcastService --> EpisodeRepository
    FeedParser ..> Podcast : creates
    FeedParser ..> Episode : creates
    AudioDownloader ..> DownloadResult : returns
    DownloadService ..> DownloadStats : returns
    PodcastService ..> IngestionResult : returns
    PipelineService ..> PipelineReport : returns
    ProcessingState ..> EpisodeRepository : validates
    Podcast --> SourceType
```

---

## 2. Component Diagram — System Architecture

```mermaid
graph TB
    subgraph "Entry Points"
        CLI["CLI<br/>python -m podflow.cli"]
        Airflow["Airflow DAG<br/>podcast_pipeline"]
        FutureAPI["FastAPI<br/>(future)"]
    end

    subgraph "Orchestration"
        Pipeline["PipelineService"]
    end

    subgraph "Services"
        IngestSvc["PodcastService"]
        DownloadSvc["DownloadService"]
        TranscribeSvc["TranscriptionService<br/>(future)"]
        SummarySvc["SummaryService<br/>(future)"]
    end

    subgraph "Ingestion"
        RSSReader["RSSFeedReader"]
        Parser["FeedParser"]
    end

    subgraph "Downloader"
        AudioDL["AudioDownloader"]
        FileMgr["FileManager"]
    end

    subgraph "Persistence"
        PodcastRepo["PodcastRepository"]
        EpisodeRepo["EpisodeRepository"]
        Models["SQLAlchemy ORM<br/>Podcast · Episode"]
        DB[("SQLite<br/>data/podflow.db")]
    end

    subgraph "Filesystem"
        AudioDir["downloads/audio/"]
        TranscriptDir["downloads/transcripts/"]
        SummaryDir["downloads/summaries/"]
    end

    subgraph "Domain"
        DomainObjs["Podcast · Episode<br/>ProcessingState<br/>SourceType"]
    end

    CLI --> Pipeline
    Airflow --> Pipeline
    FutureAPI --> Pipeline

    Pipeline --> IngestSvc
    Pipeline --> DownloadSvc
    Pipeline -.-> TranscribeSvc
    Pipeline -.-> SummarySvc

    IngestSvc --> RSSReader
    IngestSvc --> Parser
    DownloadSvc --> AudioDL
    DownloadSvc --> FileMgr
    DownloadSvc --> EpisodeRepo
    IngestSvc --> PodcastRepo
    IngestSvc --> EpisodeRepo

    RSSReader --> Parser
    Parser --> DomainObjs
    AudioDL --> FileMgr
    FileMgr --> AudioDir
    FileMgr -.-> TranscriptDir
    FileMgr -.-> SummaryDir

    PodcastRepo --> Models
    EpisodeRepo --> Models
    Models --> DB
```

---

## 3. Sequence Diagram — Full Pipeline Execution

```mermaid
sequenceDiagram
    actor User
    participant Pipeline as PipelineService
    participant Ingest as PodcastService
    participant RSS as RSSFeedReader
    participant Parser as FeedParser
    participant PRepo as PodcastRepository
    participant ERepo as EpisodeRepository
    participant DL as DownloadService
    participant Audio as AudioDownloader
    participant FM as FileManager
    participant DB as SQLite
    participant Disk as Filesystem

    User->>Pipeline: run(url, limit=2)

    %% Stage 1: Ingest
    Pipeline->>Ingest: run(url)
    Ingest->>RSS: fetch(url)
    RSS-->>Ingest: raw feed (553 entries)
    Ingest->>Parser: parse(raw)
    Parser-->>Ingest: Podcast + list[Episode]

    Ingest->>PRepo: get_or_create(podcast)
    PRepo->>DB: INSERT/UPDATE
    PRepo-->>Ingest: podcast (ORM)

    Ingest->>ERepo: bulk_upsert(episodes)
    ERepo->>DB: INSERT (skip dup GUIDs)
    ERepo-->>Ingest: 553 new

    Ingest-->>Pipeline: IngestionResult(553 found, 553 new)

    %% Stage 2: Download
    Pipeline->>DL: download_new_episodes(limit=2)
    DL->>ERepo: list_by_state(DISCOVERED)
    ERepo->>DB: SELECT
    ERepo-->>DL: [ep1, ep2, ...]

    loop For each episode (up to 2)
        DL->>FM: audio_path(episode)
        FM-->>DL: downloads/audio/ep.mp3

        alt file exists
            DL->>DL: compute SHA-256 from disk
            DL->>ERepo: update_state(DOWNLOADED)
        else download needed
            DL->>ERepo: update_state(QUEUED)
            DL->>ERepo: update_state(DOWNLOADING)
            DL->>Audio: download(url, dest)
            Audio->>Audio: stream to .part
            Audio->>Disk: write chunks + hash
            Audio->>Disk: rename .part → .mp3
            Audio-->>DL: DownloadResult(sha256, bytes)
            DL->>ERepo: update_state(DOWNLOADED, hash, size)
        end
    end

    DL->>DB: COMMIT
    DL-->>Pipeline: DownloadStats(2 downloaded, 0 failed)

    Pipeline-->>User: PipelineReport(553 discovered, 2 downloaded, 10.05s)
```

---

## 4. Deployment Diagram — Current & Future

```mermaid
graph TB
    subgraph "Local Development (Current)"
        direction TB
        subgraph "WSL2 Ubuntu 24.04"
            Python["Python 3.12<br/>.venv/"]
            AirflowS["Airflow Scheduler<br/>LocalExecutor"]
            SQLiteDB[("SQLite<br/>data/podflow.db")]
            Downloads["downloads/"]
            PodFlow["PodFlow Package<br/>~5,000 lines"]
        end

        subgraph "GitHub"
            Repo["hemanthv77/PodFlow<br/>v0.5.0"]
        end

        Python --> PodFlow
        AirflowS --> PodFlow
        PodFlow --> SQLiteDB
        PodFlow --> Downloads
    end

    subgraph "Future Production"
        direction TB
        subgraph "Cloud (AWS/GCP/Azure)"
            subgraph "Compute"
                AirflowP["Managed Airflow<br/>or K8s CronJob"]
                FastAPI["FastAPI Backend<br/>Uvicorn"]
                Workers["Worker Pods<br/>transcription, summarization"]
            end

            subgraph "Storage"
                PG[("PostgreSQL<br/>RDS / Cloud SQL")]
                S3["Object Storage<br/>S3 / GCS<br/>audio, transcripts"]
            end

            subgraph "AI Services"
                Whisper["Whisper API<br/>transcription"]
                LLM["LLM API<br/>summarization"]
            end
        end

        AirflowP --> FastAPI
        FastAPI --> PG
        FastAPI --> S3
        Workers --> Whisper
        Workers --> LLM
        Workers --> PG
        Workers --> S3
    end

    Local -.->|"git push"| Repo
    Repo -.->|"CI/CD deploy"| Production
```

---

## 5. State Machine Diagram — Episode Lifecycle

```mermaid
stateDiagram-v2
    [*] --> NEW
    NEW --> DISCOVERED

    DISCOVERED --> QUEUED
    QUEUED --> DOWNLOADING
    DOWNLOADING --> DOWNLOADED
    DOWNLOADING --> FAILED_DOWNLOAD

    DOWNLOADED --> TRANSCRIBING : future
    TRANSCRIBING --> TRANSCRIBED : future
    TRANSCRIBING --> FAILED_TRANSCRIPTION : future

    TRANSCRIBED --> SUMMARIZING : future
    SUMMARIZING --> SUMMARIZED : future
    SUMMARIZING --> FAILED_SUMMARIZATION : future

    SUMMARIZED --> EMBEDDING : future
    EMBEDDING --> EMBEDDED : future
    EMBEDDING --> FAILED_EMBEDDING : future

    EMBEDDED --> COMPLETE : future

    FAILED_DOWNLOAD --> [*]
    FAILED_TRANSCRIPTION --> [*]
    FAILED_SUMMARIZATION --> [*]
    FAILED_EMBEDDING --> [*]
    COMPLETE --> [*]
```
