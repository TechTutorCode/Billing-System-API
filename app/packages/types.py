"""Package type definitions."""

from enum import Enum


class PackageType(str, Enum):
    """Package type enumeration."""

    PPPOE = "pppoe"
    STATIC = "static"
    HOTSPOT = "hotspot"


class ValidityUnit(str, Enum):
    """Validity unit enumeration."""

    MINUTES = "minutes"
    HOURS = "hours"
    DAYS = "days"

