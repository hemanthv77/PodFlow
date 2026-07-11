"""Shared fixtures for API integration tests."""

import pytest
from fastapi.testclient import TestClient

from podflow.api.main import create_app
from podflow.database.session import SessionLocal


@pytest.fixture
def client():
    """Return a TestClient with a fresh app instance."""
    app = create_app()
    return TestClient(app)


@pytest.fixture
def db():
    """Yield a database session and roll back after test."""
    session = SessionLocal()
    yield session
    session.rollback()
    session.close()


@pytest.fixture
def valid_rss_url():
    """A valid RSS feed URL for tests."""
    return "https://talkpython.fm/episodes/rss"


@pytest.fixture
def invalid_rss_url():
    """An obviously invalid URL."""
    return "not-a-valid-url"
