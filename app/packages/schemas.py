"""Pydantic schemas for package endpoints."""

from decimal import Decimal
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.packages.types import ValidityUnit


class PackageTypeResponse(BaseModel):
    """Schema for package type response."""

    id: str
    name: str
    description: Optional[str] = None
    created_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "pppoe",
                "description": "PPPoE connection type",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class PackageCreate(BaseModel):
    """Schema for package creation request."""

    name: str = Field(..., min_length=1, max_length=255, description="Package name")
    download_speed: int = Field(..., gt=0, description="Download speed in Mbps")
    upload_speed: int = Field(..., gt=0, description="Upload speed in Mbps")
    price: Decimal = Field(..., gt=0, decimal_places=2, description="Package price")
    validity_value: int = Field(..., gt=0, description="Validity value")
    validity_unit: ValidityUnit = Field(..., description="Validity unit (minutes, hours, days)")
    data_limit_gb: Optional[int] = Field(default=None, gt=0, description="Data limit in GB (optional)")
    router_id: UUID = Field(..., description="Router ID")
    package_type_id: UUID = Field(..., description="Package type ID")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Premium 100Mbps",
                "download_speed": 100,
                "upload_speed": 50,
                "price": "99.99",
                "validity_value": 30,
                "validity_unit": "days",
                "data_limit_gb": 500,
                "router_id": "123e4567-e89b-12d3-a456-426614174000",
                "package_type_id": "123e4567-e89b-12d3-a456-426614174001"
            }
        }


class PackageUpdate(BaseModel):
    """Schema for package update request."""

    name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Package name")
    download_speed: Optional[int] = Field(default=None, gt=0, description="Download speed in Mbps")
    upload_speed: Optional[int] = Field(default=None, gt=0, description="Upload speed in Mbps")
    price: Optional[Decimal] = Field(default=None, gt=0, decimal_places=2, description="Package price")
    validity_value: Optional[int] = Field(default=None, gt=0, description="Validity value")
    validity_unit: Optional[ValidityUnit] = Field(default=None, description="Validity unit (minutes, hours, days)")
    data_limit_gb: Optional[int] = Field(default=None, gt=0, description="Data limit in GB (optional)")
    mikrotik_profile: Optional[str] = Field(default=None, description="MikroTik profile name")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Premium 200Mbps",
                "download_speed": 200,
                "upload_speed": 100,
                "price": "149.99"
            }
        }


class PackageResponse(BaseModel):
    """Schema for package response."""

    id: str
    name: str
    download_speed: int
    upload_speed: int
    price: str
    validity_value: int
    validity_unit: str
    data_limit_gb: Optional[int] = None
    router_id: str
    package_type_id: str
    package_type: PackageTypeResponse
    mikrotik_profile: Optional[str] = None
    is_active: bool
    created_at: str
    updated_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Premium 100Mbps",
                "download_speed": 100,
                "upload_speed": 50,
                "price": "99.99",
                "validity_value": 30,
                "validity_unit": "days",
                "data_limit_gb": 500,
                "router_id": "123e4567-e89b-12d3-a456-426614174001",
                "package_type_id": "123e4567-e89b-12d3-a456-426614174002",
                "package_type": {
                    "id": "123e4567-e89b-12d3-a456-426614174002",
                    "name": "pppoe",
                    "description": "PPPoE connection type",
                    "created_at": "2024-01-01T00:00:00Z"
                },
                "mikrotik_profile": None,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }

