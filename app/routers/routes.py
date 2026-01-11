"""Router API routes."""

import uuid
from typing import Dict, List

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_isp
from app.config import get_settings
from app.database import get_db
from app.isps.models import ISPDetails
from app.routers.models import Router
from app.routers.schemas import (
    RouterConfigResponse,
    RouterCreateRequest,
    RouterCreateResponse,
    RouterResponse,
)
from app.routers.services import router_service

router = APIRouter(prefix="/api/routers", tags=["Routers"])

settings = get_settings()

# Store passwords temporarily during creation (in-memory only)
# This is cleared immediately after config is returned
# In production, consider using Redis or similar for distributed systems
_router_passwords: Dict[str, str] = {}


@router.get(
    "/",
    response_model=List[RouterResponse],
    summary="List Routers",
    description="Get list of all routers for the authenticated ISP."
)
def list_routers(
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    List all routers for the authenticated ISP.

    This endpoint:
    - Returns all active routers for the ISP
    - Requires valid JWT access token
    """
    try:
        routers = (
            db.query(Router)
            .filter(
                Router.isp_id == current_isp.id,
                Router.is_active == True
            )
            .all()
        )

        router_responses = [
            RouterResponse(
                id=str(r.id),
                isp_id=str(r.isp_id),
                name=r.name,
                vpn_username=r.vpn_username,
                vpn_ip=r.vpn_ip,
                api_port=r.api_port,
                status=r.status,
                last_seen=r.last_seen.isoformat() if r.last_seen else None,
                created_at=r.created_at.isoformat() if r.created_at else ""
            )
            for r in routers
        ]

        return router_responses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve routers: {str(e)}"
        )


@router.post(
    "/",
    response_model=RouterCreateResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Router",
    description="Create a new MikroTik router and automatically set up VPN user. Returns OpenVPN config."
)
def create_router(
    request: RouterCreateRequest,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Create a new router.

    This endpoint:
    - Creates router record in database
    - Generates VPN username (router_<id>)
    - Generates strong random password
    - Creates VPN user via ovpn-user.sh script
    - Encrypts and stores password
    - Returns MikroTik OpenVPN client configuration
    """
    try:
        if not settings.OPENVPN_SERVER_IP:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="OpenVPN server IP not configured"
            )

        # Create router and VPN user
        router, vpn_password = router_service.create_router(
            db=db,
            isp=current_isp,
            name=request.name,
            openvpn_server_ip=settings.OPENVPN_SERVER_IP,
            openvpn_server_port=settings.OPENVPN_SERVER_PORT
        )

        # Generate OpenVPN config
        openvpn_config = router_service.get_router_config(
            router=router,
            openvpn_server_ip=settings.OPENVPN_SERVER_IP,
            openvpn_server_port=settings.OPENVPN_SERVER_PORT,
            vpn_password=vpn_password
        )

        # Store password temporarily for config retrieval (only during this request)
        _router_passwords[str(router.id)] = vpn_password

        router_response = RouterResponse(
            id=str(router.id),
            isp_id=str(router.isp_id),
            name=router.name,
            vpn_username=router.vpn_username,
            vpn_ip=router.vpn_ip,
            api_port=router.api_port,
            status=router.status,
            last_seen=router.last_seen.isoformat() if router.last_seen else None,
            created_at=router.created_at.isoformat() if router.created_at else ""
        )

        return RouterCreateResponse(
            status_code=status.HTTP_201_CREATED,
            message="Router created successfully",
            router=router_response,
            openvpn_config=openvpn_config
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create router: {str(e)}"
        )


@router.get(
    "/{router_id}/config",
    response_model=RouterConfigResponse,
    summary="Get Router Config",
    description="Get MikroTik OpenVPN client configuration. Only available immediately after creation."
)
def get_router_config(
    router_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Get router OpenVPN configuration.

    This endpoint:
    - Returns MikroTik OpenVPN client configuration
    - Only works immediately after router creation
    - Never returns password in plaintext after initial creation
    """
    try:
        router_uuid = uuid.UUID(router_id)

        # Get router
        router = (
            db.query(Router)
            .filter(
                Router.id == router_uuid,
                Router.isp_id == current_isp.id,
                Router.is_active == True
            )
            .first()
        )

        if not router:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Router not found"
            )

        # Check if password is still in temporary storage (only during creation)
        vpn_password = _router_passwords.get(router_id)
        if not vpn_password:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Configuration can only be retrieved immediately after router creation. Password is not stored in plaintext."
            )

        # Generate config
        openvpn_config = router_service.get_router_config(
            router=router,
            openvpn_server_ip=settings.OPENVPN_SERVER_IP,
            openvpn_server_port=settings.OPENVPN_SERVER_PORT,
            vpn_password=vpn_password
        )

        return RouterConfigResponse(
            status_code=status.HTTP_200_OK,
            message="Router configuration retrieved successfully",
            openvpn_config=openvpn_config
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid router ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve router config: {str(e)}"
        )


@router.delete(
    "/{router_id}",
    status_code=status.HTTP_200_OK,
    summary="Delete Router",
    description="Delete router and remove VPN user. Router is marked inactive."
)
def delete_router(
    router_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Delete router.

    This endpoint:
    - Removes VPN user via ovpn-user.sh del command
    - Marks router as inactive (soft delete)
    - Only accessible by router owner (ISP)
    """
    try:
        router_uuid = uuid.UUID(router_id)

        # Get router
        router = (
            db.query(Router)
            .filter(
                Router.id == router_uuid,
                Router.isp_id == current_isp.id,
                Router.is_active == True
            )
            .first()
        )

        if not router:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Router not found"
            )

        # Delete router and VPN user
        router_service.delete_router(db=db, router=router)

        # Remove password from temporary storage if exists
        _router_passwords.pop(router_id, None)

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Router deleted successfully"
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid router ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete router: {str(e)}"
        )

