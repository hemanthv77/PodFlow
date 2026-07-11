"""PodFlow API — FastAPI transport layer.

All business logic lives in `podflow.services`. This package provides
only routing, serialization, middleware, and dependency injection.
"""

from .main import create_app

__all__ = ["create_app"]
