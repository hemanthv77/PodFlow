"""
Application settings loaded from environment variables and .env file.

Uses pydantic-settings for validation and type coercion.
"""

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for PodFlow, loaded from .env and environment."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ---- Application ----
    app_name: str = "PodFlow"

    # ---- Paths ----
    database_path: str = "data/podflow.db"
    download_dir: str = "downloads"

    # ---- RSS ----
    rss_url: str = "https://www.marketplace.org/feed/podcast/marketplace/"

    # ---- Logging ----
    log_level: str = "INFO"

    # ---- Download ----
    download_timeout: int = 120
    """HTTP timeout (seconds) for audio downloads."""

    download_max_retries: int = 3
    """Number of retry attempts for failed downloads."""

    # ---- RSS Fetch ----
    rss_fetch_timeout: int = 30
    """HTTP timeout (seconds) for RSS feed requests."""

    @property
    def database_url(self) -> str:
        """Build the SQLAlchemy connection URL for SQLite."""
        db_path = Path(self.database_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        return f"sqlite:///{db_path.resolve()}"

    @property
    def download_path(self) -> Path:
        """Return the resolved download directory as a Path."""
        p = Path(self.download_dir)
        p.mkdir(parents=True, exist_ok=True)
        return p.resolve()


# Singleton instance -- import this everywhere
settings = Settings()
