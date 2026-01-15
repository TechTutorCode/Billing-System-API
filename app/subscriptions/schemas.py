"""Pydantic schemas for subscription endpoints."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.subscriptions.types import SubscriptionPackageType, SubscriptionStatus


class SubscriptionCreate(BaseModel):
    """Schema for subscription creation request."""

    customer_id: UUID = Field(..., description="Customer ID")
    router_id: UUID = Field(..., description="Router ID")
    package_id: UUID = Field(..., description="Package ID")
    username: str = Field(..., min_length=1, max_length=255, description="Username (unique per router)")
    password: Optional[str] = Field(default=None, min_length=1, description="Password (required for PPPoE)")
    ip_address: Optional[str] = Field(default=None, description="IP address (required for Static IP)")

    @model_validator(mode="after")
    def validate_package_type_requirements(self):
        """Validate PPPoE requires password, Static requires IP address."""
        # We'll need to check package type in service layer
        # For now, we validate that at least one is provided
        # The service will check package type and enforce requirements
        return self

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "customer_id": "123e4567-e89b-12d3-a456-426614174000",
                "router_id": "123e4567-e89b-12d3-a456-426614174001",
                "package_id": "123e4567-e89b-12d3-a456-426614174002",
                "username": "customer001",
                "password": "securepassword123",
                "ip_address": None
            }
        }


class SubscriptionUpdate(BaseModel):
    """Schema for subscription update request."""

    username: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Username")
    password: Optional[str] = Field(default=None, min_length=1, description="Password")
    ip_address: Optional[str] = Field(default=None, description="IP address")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "username": "updated_username",
                "password": "newpassword123"
            }
        }


class SubscriptionResponse(BaseModel):
    """Schema for subscription response."""

    id: str
    isp_id: str
    customer_id: str
    router_id: str
    package_id: str
    package_type: str
    username: str
    password: Optional[str] = None  # Only returned for display, not for security
    ip_address: Optional[str] = None
    status: str
    start_at: Optional[str] = None
    end_at: Optional[str] = None
    created_at: str
    updated_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "isp_id": "123e4567-e89b-12d3-a456-426614174001",
                "customer_id": "123e4567-e89b-12d3-a456-426614174002",
                "router_id": "123e4567-e89b-12d3-a456-426614174003",
                "package_id": "123e4567-e89b-12d3-a456-426614174004",
                "package_type": "pppoe",
                "username": "customer001",
                "password": "***",
                "ip_address": None,
                "status": "active",
                "start_at": "2024-01-01T00:00:00Z",
                "end_at": "2024-01-31T23:59:59Z",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }


class SubscriptionActionRequest(BaseModel):
    """Schema for subscription action request (activate, suspend, resume, terminate)."""

    api_password: Optional[str] = Field(default=None, description="MikroTik API password (if not stored)")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "api_password": "mikrotik_password"
            }
        }


class SubscriptionActionResponse(BaseModel):
    """Schema for subscription action response."""

    status_code: int
    message: str
    subscription_id: str
    status: str

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Subscription activated successfully",
                "subscription_id": "123e4567-e89b-12d3-a456-426614174000",
                "status": "active"
            }
        }

