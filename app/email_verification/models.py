"""Email Verification database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class EmailVerification(Base):
    """Email Verification table model."""

    __tablename__ = "Email_Verification"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    token = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship to ISP
    isp = relationship("ISPDetails", backref="email_verifications")

    def __repr__(self):
        return f"<EmailVerification(id={self.id}, isp_id={self.isp_id}, token={self.token[:10]}...)>"


