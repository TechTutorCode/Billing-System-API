"""Refresh token database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String, Boolean
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RefreshToken(Base):
    """Refresh token table model."""

    __tablename__ = "Refresh_Token"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    revoked = Column(Boolean, default=False, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    revoked_at = Column(DateTime(timezone=True), nullable=True)

    # Relationship to ISP
    isp = relationship("ISPDetails", backref="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(id={self.id}, isp_id={self.isp_id}, token={self.token[:10]}..., revoked={self.revoked})>"


