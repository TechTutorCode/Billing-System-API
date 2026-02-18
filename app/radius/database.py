"""
RADIUS database connection (separate from billing).

Uses RADIUS_DATABASE_URL. Do NOT auto-create tables; FreeRADIUS creates them.
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

from app.config import get_settings

_settings = get_settings()

# Separate engine for RADIUS database only
radius_engine = create_engine(
    _settings.RADIUS_DATABASE_URL,
    pool_pre_ping=True,
    pool_size=5,
    max_overflow=10,
)

# Session factory for RADIUS (do not use for billing tables)
RadiusSessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=radius_engine,
)

# Declarative base for RADIUS models only (separate metadata from billing Base)
RadiusBase = declarative_base()


def get_radius_db():
    """
    Dependency that yields a RADIUS database session.
    Use only for RADIUS tables (radcheck, radreply, radusergroup).
    """
    db = RadiusSessionLocal()
    try:
        yield db
    finally:
        db.close()
