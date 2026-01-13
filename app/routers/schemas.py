"""Pydantic schemas for router endpoints."""

from typing import Optional
from pydantic import BaseModel, Field


class RouterCreateRequest(BaseModel):
    """Schema for router creation request."""

    name: str = Field(..., min_length=1, max_length=255, description="Router name")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "name": "Main Office Router"
            }
        }


class RouterResponse(BaseModel):
    """Schema for router response."""

    id: str
    isp_id: str
    name: str
    vpn_username: str
    vpn_ip: Optional[str] = None
    api_port: int
    status: str
    last_seen: Optional[str] = None
    created_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "isp_id": "123e4567-e89b-12d3-a456-426614174001",
                "name": "Main Office Router",
                "vpn_username": "router_12345678",
                "vpn_ip": "10.8.0.5",
                "api_port": 8728,
                "status": "online",
                "last_seen": "2024-01-01T12:00:00Z",
                "created_at": "2024-01-01T00:00:00Z"
            }
        }


class RouterCreateResponse(BaseModel):
    """Schema for router creation response."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    router: RouterResponse
    openvpn_config: str = Field(..., description="MikroTik OpenVPN client configuration")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 201,
                "message": "Router created successfully",
                "router": {
                    "id": "123e4567-e89b-12d3-a456-426614174000",
                    "isp_id": "123e4567-e89b-12d3-a456-426614174001",
                    "name": "Main Office Router",
                    "vpn_username": "router_12345678",
                    "vpn_ip": None,
                    "api_port": 8728,
                    "status": "pending",
                    "last_seen": None,
                    "created_at": "2024-01-01T00:00:00Z"
                },
                "openvpn_config": "/interface ovpn-client add ..."
            }
        }


class RouterConfigResponse(BaseModel):
    """Schema for router config response."""

    status_code: int = Field(..., description="HTTP status code")
    message: str
    openvpn_config: str = Field(..., description="MikroTik OpenVPN client configuration")

    class Config:
        """Pydantic config."""

        json_schema_extra = {
            "example": {
                "status_code": 200,
                "message": "Router configuration retrieved successfully",
                "openvpn_config": "/interface ovpn-client add ..."
            }
        }


class RouterStatusHistoryResponse(BaseModel):
    """Schema for router status history response."""

    id: str
    router_id: str
    status: str
    vpn_ip: Optional[str] = None
    api_port: int
    mikrotik_api_accessible: bool
    connected_since: Optional[str] = None
    recorded_at: str

    class Config:
        """Pydantic config."""

        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": "123e4567-e89b-12d3-a456-426614174000",
                "router_id": "123e4567-e89b-12d3-a456-426614174001",
                "status": "online",
                "vpn_ip": "10.8.0.5",
                "api_port": 8728,
                "mikrotik_api_accessible": True,
                "connected_since": "2024-01-01T11:00:00Z",
                "recorded_at": "2024-01-01T12:00:00Z"
            }
        }

