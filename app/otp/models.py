"""Login OTP database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class LoginOTP(Base):
    """Login OTP table model."""

    __tablename__ = "Login_OTP"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    otp_code = Column(String(6), nullable=False, index=True)
    session_id = Column(String, unique=True, nullable=False, index=True)
    expires_at = Column(DateTime(timezone=True), nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    attempts = Column(Integer, default=0, nullable=False)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship to ISP
    isp = relationship("ISPDetails", backref="login_otps")

    def __repr__(self):
        return f"<LoginOTP(id={self.id}, isp_id={self.isp_id}, otp_code={self.otp_code[:2]}**, session_id={self.session_id[:10]}...)>"


