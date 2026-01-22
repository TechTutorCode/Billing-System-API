"""Hotspot database models."""

from datetime import datetime, timezone

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class HotspotPackage(Base):
    """Hotspot package table model."""

    __tablename__ = "hotspot_packages"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    name = Column(String, nullable=False)
    download_speed = Column(Integer, nullable=False)  # Kbps
    upload_speed = Column(Integer, nullable=False)  # Kbps
    validity_minutes = Column(Integer, nullable=False)  # Session timeout in minutes
    shared_users = Column(Integer, default=1, nullable=False)  # Number of concurrent users
    router_id = Column(
        UUID(as_uuid=True),
        ForeignKey("Router.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    mikrotik_profile_name = Column(String, nullable=True, index=True)
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )

    # Relationships
    router = relationship("Router", backref="hotspot_packages")
    vouchers = relationship("HotspotVoucher", backref="package", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<HotspotPackage(id={self.id}, name={self.name}, router_id={self.router_id})>"


class HotspotVoucher(Base):
    """Hotspot voucher (MAC-based user) table model."""

    __tablename__ = "hotspot_vouchers"

    id = Column(Integer, primary_key=True, autoincrement=True, index=True)
    mac_address = Column(String, nullable=False, index=True)  # MAC address in format XX:XX:XX:XX:XX:XX
    package_id = Column(
        Integer,
        ForeignKey("hotspot_packages.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    profile_name = Column(String, nullable=False)  # MikroTik profile name
    is_active = Column(Boolean, default=True, nullable=False, index=True)
    created_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=True, index=True)  # Optional expiry date

    # Unique constraint: MAC address must be unique per router (via package)
    __table_args__ = (
        UniqueConstraint("mac_address", "package_id", name="uq_mac_package"),
    )

    def __repr__(self):
        return f"<HotspotVoucher(id={self.id}, mac_address={self.mac_address}, package_id={self.package_id})>"
