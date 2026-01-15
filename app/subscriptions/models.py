"""Subscription database models."""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class SubscriptionStatus(str, Enum):
    """Subscription status enumeration."""

    PENDING = "pending"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    EXPIRED = "expired"
    TERMINATED = "terminated"


class SubscriptionPackageType(str, Enum):
    """Subscription package type enumeration (PPPoE or Static only)."""

    PPPOE = "pppoe"
    STATIC = "static"


class Subscription(Base):
    """Subscription table model."""

    __tablename__ = "subscriptions"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    customer_id = Column(
        UUID(as_uuid=True),
        ForeignKey("customers.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    router_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Router.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    package_id = Column(
        UUID(as_uuid=True),
        ForeignKey("service_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    package_type = Column(
        SQLEnum(SubscriptionPackageType, name="subscription_package_type"),
        nullable=False,
        index=True
    )
    username = Column(String, nullable=False)
    password = Column(String, nullable=True)  # Required for PPPoE
    ip_address = Column(String, nullable=True)  # Required for Static
    status = Column(
        SQLEnum(SubscriptionStatus, name="subscription_status"),
        default=SubscriptionStatus.PENDING.value,
        nullable=False,
        index=True
    )
    start_at = Column(DateTime(timezone=True), nullable=True)
    end_at = Column(DateTime(timezone=True), nullable=True, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    isp = relationship("ISPDetails", backref="subscriptions")
    customer = relationship("Customer", backref="subscriptions")
    router = relationship("Router", backref="subscriptions")
    package = relationship("ServicePackage", backref="subscriptions")

    # Unique constraint: username must be unique per router
    __table_args__ = (
        UniqueConstraint("router_id", "username", name="uq_router_username"),
    )

    def __repr__(self):
        return f"<Subscription(id={self.id}, customer_id={self.customer_id}, router_id={self.router_id}, status={self.status})>"

