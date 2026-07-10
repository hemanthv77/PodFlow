"""Shared fixtures and helpers for PodFlow tests."""

from pathlib import Path

import pytest


@pytest.fixture
def temp_dir(tmp_path: Path) -> Path:
    """Return a temporary directory for filesystem tests."""
    d = tmp_path / "downloads"
    d.mkdir()
    return d


@pytest.fixture
def sample_episode_kwargs() -> dict:
    """Standard episode kwargs used across multiple test modules."""
    return {
        "title": "#554: Trustworthy AI in Healthcare & Longevity!",
        "guid": "abc-123-def",
        "audio_url": "https://example.com/episodes/554.mp3",
    }
