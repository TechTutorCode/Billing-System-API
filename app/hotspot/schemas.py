"""Pydantic schemas for hotspot endpoints."""

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class HotspotPackageCreate(BaseModel):
    """Schema for hotspot package creation request."""

    name: str = Field(..., min_length=1, max_length=255, description="Package name")
    download_speed: int = Field(..., gt=0, description="Download speed in Kbps")
    upload_speed: int = Field(..., gt=0, description="Upload speed in Kbps")
    validity_minutes: int = Field(..., gt=0, description="Session timeout in minutes")
    shared_users: int = Field(default=1, ge=1, description="Number of concurrent users allowed")
    router_id: str = Field(..., description="Router ID (UUID)")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Hotspot Basic 1 Hour",
                "download_speed": 10240,  # 10 Mbps in Kbps
                "upload_speed": 5120,  # 5 Mbps in Kbps
                "validity_minutes": 60,
                "shared_users": 1,
                "router_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class HotspotPackageUpdate(BaseModel):
    """Schema for hotspot package update request."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Package name")
    download_speed: Optional[int] = Field(default=None, gt=0, description="Download speed in Kbps")
    upload_speed: Optional[int] = Field(default=None, gt=0, description="Upload speed in Kbps")
    validity_minutes: Optional[int] = Field(default=None, gt=0, description="Session timeout in minutes")
    shared_users: Optional[int] = Field(default=None, ge=1, description="Number of concurrent users allowed")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Hotspot Premium 2 Hours",
                "download_speed": 20480,
                "upload_speed": 10240,
                "validity_minutes": 120,
                "shared_users": 2
            }
        }


class HotspotPackageResponse(BaseModel):
    """Schema for hotspot package response."""

    id: int
    name: str
    download_speed: int
    upload_speed: int
    validity_minutes: int
    shared_users: int
    router_id: str
    mikrotik_profile_name: Optional[str] = None
    is_active: bool
    created_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Hotspot Basic 1 Hour",
                "download_speed": 10240,
                "upload_speed": 5120,
                "validity_minutes": 60,
                "shared_users": 1,
                "router_id": "123e4567-e89b-12d3-a456-426614174000",
                "mikrotik_profile_name": "hotspot_pkg_1",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class HotspotVoucherCreate(BaseModel):
    """Schema for hotspot voucher (MAC user) creation request."""

    mac_address: str = Field(..., description="MAC address (format: XX:XX:XX:XX:XX:XX)")
    package_id: int = Field(..., gt=0, description="Hotspot package ID")
    expires_at: Optional[datetime] = Field(default=None, description="Optional expiry date/time")

    @field_validator("mac_address")
    @classmethod
    def validate_mac_address(cls, v: str) -> str:
        """Validate MAC address format."""
        import re
        # Remove common separators and convert to uppercase
        mac = v.replace(":", "").replace("-", "").replace(".", "").upper()
        # Check if it's 12 hex characters
        if not re.match(r"^[0-9A-F]{12}$", mac):
            raise ValueError("Invalid MAC address format. Expected format: XX:XX:XX:XX:XX:XX")
        # Return in standard format XX:XX:XX:XX:XX:XX
        return ":".join([mac[i:i+2] for i in range(0, 12, 2)])

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "mac_address": "00:1B:44:11:3A:B7",
                "package_id": 1,
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }


class HotspotVoucherResponse(BaseModel):
    """Schema for hotspot voucher response."""

    id: int
    mac_address: str
    package_id: int
    profile_name: str
    is_active: bool
    created_at: str
    expires_at: Optional[str] = None

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "mac_address": "00:1B:44:11:3A:B7",
                "package_id": 1,
                "profile_name": "hotspot_pkg_1",
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "expires_at": "2024-12-31T23:59:59Z"
            }
        }
