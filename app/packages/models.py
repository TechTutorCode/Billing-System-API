"""Package database models."""

import uuid
from datetime import datetime, timezone
from decimal import Decimal

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class PackageType(Base):
    """Package type table model."""

    __tablename__ = "package_types"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, unique=True, nullable=False, index=True)
    description = Column(String, nullable=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationship to ServicePackage
    service_packages = relationship("ServicePackage", backref="package_type")

    def __repr__(self):
        return f"<PackageType(id={self.id}, name={self.name})>"


class ServicePackage(Base):
    """Service package table model."""

    __tablename__ = "service_packages"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    name = Column(String, nullable=False)
    download_speed = Column(Integer, nullable=False)  # Mbps
    upload_speed = Column(Integer, nullable=False)  # Mbps
    price = Column(Numeric(10, 2), nullable=False)
    validity_value = Column(Integer, nullable=False)  # > 0
    validity_unit = Column(String, nullable=False)  # minutes, hours, days
    data_limit_gb = Column(Integer, nullable=True)
    router_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Router.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    package_type_id = Column(
        UUID(as_uuid=True),
        ForeignKey("package_types.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    mikrotik_profile = Column(String, nullable=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
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

    # Relationship to Router
    router = relationship("Router", backref="service_packages")

    # Unique constraint: (router_id, name, package_type_id)
    __table_args__ = (
        UniqueConstraint("router_id", "name", "package_type_id", name="uq_router_name_package_type"),
    )

    def __repr__(self):
        return f"<ServicePackage(id={self.id}, name={self.name}, router_id={self.router_id})>"

