"""Pydantic schemas for ISP profile endpoints."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, HttpUrl


class ISPProfileResponse(BaseModel):
    """Schema for ISP profile response."""

    id: str
    name: str
    email: str
    phone: Optional[str] = None
    location: Optional[str] = None
    logo_url: Optional[str] = None
    website: Optional[str] = None
    is_verified: bool
    is_active: bool
    created_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "name": "Acme Internet Services",
                "email": "admin@acme.com",
                "phone": "+1234567890",
                "location": "New York, USA",
                "logo_url": "https://example.com/logo.png",
                "website": "https://acme.com",
                "is_verified": True,
                "is_active": True,
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class ISPProfileUpdateRequest(BaseModel):
    """Schema for ISP profile update request (for JSON body without file)."""

    name: Optional[str] = Field(None, min_length=1, max_length=255, description="ISP name")
    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    location: Optional[str] = Field(None, max_length=255, description="Location")
    website: Optional[str] = Field(None, max_length=255, description="Website URL")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Acme Internet Services Updated",
                "phone": "+1234567890",
                "location": "Los Angeles, USA",
                "website": "https://acme-updated.com"
            }
        }


class ISPProfileCompleteRequest(BaseModel):
    """Schema for ISP profile completion request (for JSON body without file)."""

    phone: Optional[str] = Field(None, max_length=50, description="Phone number")
    location: Optional[str] = Field(None, max_length=255, description="Location")
    website: Optional[str] = Field(None, max_length=255, description="Website URL")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "phone": "+1234567890",
                "location": "New York, USA",
                "website": "https://acme.com"
            }
        }


class ISPProfileUpdateResponse(BaseModel):
    """Schema for ISP profile update response."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    profile: ISPProfileResponse

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Profile updated successfully",
                "profile": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Acme Internet Services Updated",
                    "email": "admin@acme.com",
                    "phone": "+1234567890",
                    "location": "Los Angeles, USA",
                    "logo_url": "https://example.com/new-logo.png",
                    "website": "https://acme-updated.com",
                    "is_verified": True,
                    "is_active": True,
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }
        }


class ISPProfileCompleteResponse(BaseModel):
    """Schema for ISP profile completion response."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    profile: ISPProfileResponse

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Profile completed successfully",
                "profile": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "name": "Acme Internet Services",
                    "email": "admin@acme.com",
                    "phone": "+1234567890",
                    "location": "New York, USA",
                    "logo_url": "https://example.com/logo.png",
                    "website": "https://acme.com",
                    "is_verified": True,
                    "is_active": True,
                    "created_at": "2024-01-01T00:00:00Z"
                }
            }
        }

