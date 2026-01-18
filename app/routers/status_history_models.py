"""Router status history database model."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class RouterStatusHistory(Base):
    """Router status history table model.
    
    Records the status of each router for every monitoring cycle.
    This allows tracking status changes over time.
    """

    __tablename__ = "Router_Status_History"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    router_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Router.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    status = Column(String, nullable=False, index=True)
    vpn_ip = Column(String, nullable=True)
    api_port = Column(Integer, default=8728, nullable=False)
    mikrotik_api_accessible = Column(Boolean, default=False, nullable=False)
    connected_since = Column(DateTime(timezone=True), nullable=True)
    last_seen = Column(DateTime(timezone=True), nullable=True)
    recorded_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
        index=True
    )

    # Relationship to Router
    router = relationship("Router", backref="status_history")

    def __repr__(self):
        return f"<RouterStatusHistory(id={self.id}, router_id={self.router_id}, status={self.status}, last_seen={self.last_seen}, recorded_at={self.recorded_at})>"

