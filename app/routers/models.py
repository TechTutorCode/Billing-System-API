"""Router database model."""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RouterStatus(str, Enum):
    """Router status enumeration."""

    PENDING = "pending"
    VPN_CONNECTED = "vpn_connected"
    ONLINE = "online"
    OFFLINE = "offline"


class Router(Base):
    """Router table model."""

    __tablename__ = "Router"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    name = Column(String, nullable=False)
    vpn_username = Column(String, unique=True, nullable=False, index=True)
    vpn_password_encrypted = Column(String, nullable=False)
    vpn_ip = Column(String, nullable=True, index=True)
    api_port = Column(Integer, default=8728, nullable=False)
    mikrotik_api_username = Column(String, default="admin", nullable=False)
    mikrotik_api_password_encrypted = Column(String, nullable=True)
    status = Column(
        String,
        default=RouterStatus.PENDING.value,
        nullable=False,
        index=True
    )
    last_seen = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationship to ISP
    isp = relationship("ISPDetails", backref="routers")

    def __repr__(self):
        return f"<Router(id={self.id}, name={self.name}, vpn_username={self.vpn_username}, status={self.status})>"

