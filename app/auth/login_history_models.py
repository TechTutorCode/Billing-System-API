"""Login history database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Column, DateTime, ForeignKey, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class LoginHistory(Base):
    """Login history table model.
    
    Records all successful login attempts for ISPs.
    This allows tracking login activity and security auditing.
    """

    __tablename__ = "Login_History"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    ip_address = Column(String, nullable=True)
    user_agent = Column(String, nullable=True)
    login_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationship to ISP
    isp = relationship("ISPDetails", backref="login_history")

    def __repr__(self):
        return f"<LoginHistory(id={self.id}, isp_id={self.isp_id}, login_at={self.login_at})>"

