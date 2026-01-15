"""Customer database models."""

import uuid
from datetime import datetime, timezone
from enum import Enum

from sqlalchemy import Column, DateTime, Enum as SQLEnum, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship

from app.database import Base


class CustomerStatus(str, Enum):
    """Customer status enumeration."""

    ACTIVE = "active"
    SUSPENDED = "suspended"
    TERMINATED = "terminated"


class Customer(Base):
    """Customer table model."""

    __tablename__ = "customers"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4, index=True)
    isp_id = Column(
        UUID(as_uuid=True),
        ForeignKey("ISP_DETAILS.id", ondelete="CASCADE"),
        nullable=False,
        index=True
    )
    account_number = Column(String, unique=True, nullable=False, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    email = Column(String, nullable=True, index=True)
    phone = Column(String, nullable=True, index=True)
    id_number = Column(String, nullable=True)
    address = Column(String, nullable=True)
    password_hash = Column(Text, nullable=False)
    status = Column(
        SQLEnum(CustomerStatus, name="customer_status"),
        default=CustomerStatus.ACTIVE.value,
        nullable=False,
        index=True
    )
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

    # Relationship to ISP
    isp = relationship("ISPDetails", backref="customers")

    def __repr__(self):
        return f"<Customer(id={self.id}, account_number={self.account_number}, name={self.first_name} {self.last_name}, status={self.status})>"

