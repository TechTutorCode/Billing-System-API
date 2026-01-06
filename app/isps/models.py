"""ISP Details database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, String, Text
from sqlalchemy.dialects.postgresql import UUID

from app.database import Base


class ISPDetails(Base):
    """ISP Details table model."""

    __tablename__ = "ISP_DETAILS"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    email = Column(String, unique=True, nullable=False, index=True)
    phone = Column(String, nullable=True)
    location = Column(String, nullable=True)
    logo_url = Column(Text, nullable=True)
    website = Column(String, nullable=True)
    password_hash = Column(Text, nullable=False)
    is_verified = Column(Boolean, default=False, nullable=False)
    is_active = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    def __repr__(self):
        return f"<ISPDetails(id={self.id}, email={self.email}, name={self.name})>"

