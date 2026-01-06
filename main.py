# Import app from app.main to maintain compatibility with Dockerfile
from app.main import app

__all__ = ["app"]
