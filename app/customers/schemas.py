"""Pydantic schemas for customer endpoints."""

from typing import Optional
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


class CustomerCreate(BaseModel):
    """Schema for customer creation request."""

    first_name: str = Field(..., min_length=1, max_length=255, description="Customer first name")
    last_name: str = Field(..., min_length=1, max_length=255, description="Customer last name")
    email: Optional[EmailStr] = Field(default=None, description="Customer email address")
    phone: Optional[str] = Field(default=None, max_length=50, description="Customer phone number")
    id_number: Optional[str] = Field(default=None, max_length=100, description="Customer ID number")
    address: Optional[str] = Field(default=None, max_length=500, description="Customer address")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number contains only digits."""
        if v is not None:
            # Remove common phone formatting characters
            cleaned = v.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")
            if not cleaned.isdigit():
                raise ValueError("Phone number must contain only digits")
            return cleaned
        return v

    @model_validator(mode="after")
    def validate_contact_required(self):
        """Ensure at least one contact method (email or phone) is provided."""
        if not self.email and not self.phone:
            raise ValueError("Either email or phone must be provided")
        return self

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "1234567890",
                "id_number": "ID123456",
                "address": "123 Main Street, City"
            }
        }


class CustomerUpdate(BaseModel):
    """Schema for customer update request."""

    first_name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Customer first name")
    last_name: Optional[str] = Field(default=None, min_length=1, max_length=255, description="Customer last name")
    email: Optional[EmailStr] = Field(default=None, description="Customer email address")
    phone: Optional[str] = Field(default=None, max_length=50, description="Customer phone number")
    id_number: Optional[str] = Field(default=None, max_length=100, description="Customer ID number")
    address: Optional[str] = Field(default=None, max_length=500, description="Customer address")
    status: Optional[str] = Field(default=None, description="Customer status (active, suspended, terminated)")

    @field_validator("phone")
    @classmethod
    def validate_phone(cls, v: Optional[str]) -> Optional[str]:
        """Validate phone number contains only digits."""
        if v is not None:
            # Remove common phone formatting characters
            cleaned = v.replace("-", "").replace(" ", "").replace("(", "").replace(")", "").replace("+", "")
            if not cleaned.isdigit():
                raise ValueError("Phone number must contain only digits")
            return cleaned
        return v

    @field_validator("status")
    @classmethod
    def validate_status(cls, v: Optional[str]) -> Optional[str]:
        """Validate status value."""
        if v is not None:
            valid_statuses = ["active", "suspended", "terminated"]
            if v.lower() not in valid_statuses:
                raise ValueError(f"Status must be one of: {', '.join(valid_statuses)}")
            return v.lower()
        return v

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "1234567890",
                "status": "active"
            }
        }


class ChangePasswordRequest(BaseModel):
    """Schema for customer password change request."""

    current_password: str = Field(..., min_length=1, description="Current password")
    new_password: str = Field(..., min_length=6, description="New password (minimum 6 characters)")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "current_password": "cust001",
                "new_password": "newSecurePassword123"
            }
        }


class CustomerResponse(BaseModel):
    """Schema for customer response."""

    id: str
    isp_id: str
    account_number: str
    first_name: str
    last_name: str
    email: Optional[str] = None
    phone: Optional[str] = None
    id_number: Optional[str] = None
    address: Optional[str] = None
    status: str
    created_at: str
    updated_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "isp_id": "123e4567-e89b-12d3-a456-426614174001",
                "account_number": "cust001",
                "first_name": "John",
                "last_name": "Doe",
                "email": "john.doe@example.com",
                "phone": "1234567890",
                "id_number": "ID123456",
                "address": "123 Main Street, City",
                "status": "active",
                "created_at": "2024-01-01T00:00:00Z",
                "updated_at": "2024-01-01T00:00:00Z"
            }
        }

