"""Pydantic schemas for authentication endpoints."""

from pydantic import BaseModel, EmailStr, Field


class ISPRegisterRequest(BaseModel):
    """Schema for ISP registration request."""

    name: str = Field(..., min_length=1, max_length=255, description="ISP name")
    email: EmailStr = Field(..., description="ISP email address")
    password: str = Field(
        ...,
        min_length=8,
        max_length=100,
        description="Password (minimum 8 characters)"
    )

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Acme Internet Services",
                "email": "admin@acme.com",
                "password": "SecurePass123!"
            }
        }


class ISPRegisterResponse(BaseModel):
    """Schema for ISP registration response."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    isp_id: str

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 201,
                "message": "Registration successful. Please check your email to verify your account.",
                "isp_id": "123e4567-e89b-12d3-a456-426614174000"
            }
        }


class EmailVerifyResponse(BaseModel):
    """Schema for email verification response."""

    status_code: int = Field(..., description="HTTP status code")
    message: str

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Email verified successfully. Your account is now active."
            }
        }


class ISPLoginRequest(BaseModel):
    """Schema for ISP login request (first step - email + password)."""

    email: EmailStr = Field(..., description="ISP email address")
    password: str = Field(..., description="Password")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "email": "admin@acme.com",
                "password": "SecurePass123!"
            }
        }


class ISPLoginResponse(BaseModel):
    """Schema for ISP login response (first step - OTP sent)."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    session_id: str = Field(..., description="Session ID for OTP verification")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "OTP sent to your email. Please check and enter the OTP to complete login.",
                "session_id": "550e8400-e29b-41d4-a716-446655440000"
            }
        }


class ISPLoginOTPRequest(BaseModel):
    """Schema for ISP login OTP verification request."""

    session_id: str = Field(..., description="Session ID from login response")
    otp: str = Field(..., min_length=6, max_length=6, description="6-digit OTP code")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "session_id": "550e8400-e29b-41d4-a716-446655440000",
                "otp": "123456"
            }
        }


class ISPLoginOTPResponse(BaseModel):
    """Schema for ISP login OTP verification response (returns JWT tokens)."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    access_token: str = Field(..., description="JWT access token")
    refresh_token: str = Field(..., description="JWT refresh token")
    token_type: str = Field(default="bearer", description="Token type")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Login successful",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }


class RefreshTokenRequest(BaseModel):
    """Schema for refresh token request."""

    refresh_token: str = Field(..., description="Refresh token")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "refresh_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
            }
        }


class RefreshTokenResponse(BaseModel):
    """Schema for refresh token response (returns new access token)."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    access_token: str = Field(..., description="New JWT access token")
    token_type: str = Field(default="bearer", description="Token type")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Access token refreshed successfully",
                "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
                "token_type": "bearer"
            }
        }

