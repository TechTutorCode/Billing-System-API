"""Subscription type definitions."""

from enum import Enum


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

