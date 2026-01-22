"""Hotspot API routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_isp
from app.database import get_db
from app.isps.models import ISPDetails
from app.hotspot.schemas import (
    HotspotPackageCreate,
    HotspotPackageResponse,
    HotspotPackageUpdate,
    HotspotVoucherCreate,
    HotspotVoucherResponse
)
from app.hotspot.service import hotspot_service

router = APIRouter(prefix="/hotspot", tags=["Hotspot"])


# ==========================
# Package Endpoints
# ==========================

@router.post(
    "/packages",
    response_model=HotspotPackageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Hotspot Package",
    description="Create a new hotspot package and sync profile to MikroTik router."
)
def create_hotspot_package(
    request: HotspotPackageCreate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Create a new hotspot package.

    This endpoint:
    - Creates a hotspot package in the database
    - Creates a MikroTik hotspot profile on the router
    - Requires valid JWT access token
    - Sets package status to 'active' by default
    """
    try:
        package = hotspot_service.create_package(
            db=db,
            isp_id=current_isp.id,
            package_data=request.model_dump()
        )

        return HotspotPackageResponse(
            id=package.id,
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            validity_minutes=package.validity_minutes,
            shared_users=package.shared_users,
            router_id=str(package.router_id),
            mikrotik_profile_name=package.mikrotik_profile_name,
            is_active=package.is_active,
            created_at=package.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create hotspot package: {str(e)}"
        )


@router.get(
    "/packages",
    response_model=List[HotspotPackageResponse],
    summary="List Hotspot Packages",
    description="Get list of hotspot packages with optional filters."
)
def list_hotspot_packages(
    active_only: bool = Query(default=True, description="Return only active packages"),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    List hotspot packages.

    This endpoint:
    - Returns packages for the authenticated ISP
    - Supports filtering by active status
    - Requires valid JWT access token
    """
    try:
        packages = hotspot_service.get_packages(
            db=db,
            isp_id=current_isp.id,
            active_only=active_only
        )

        return [
            HotspotPackageResponse(
                id=p.id,
                name=p.name,
                download_speed=p.download_speed,
                upload_speed=p.upload_speed,
                validity_minutes=p.validity_minutes,
                shared_users=p.shared_users,
                router_id=str(p.router_id),
                mikrotik_profile_name=p.mikrotik_profile_name,
                is_active=p.is_active,
                created_at=p.created_at.isoformat()
            )
            for p in packages
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve hotspot packages: {str(e)}"
        )


@router.get(
    "/packages/{package_id}",
    response_model=HotspotPackageResponse,
    summary="Get Hotspot Package",
    description="Get hotspot package details by ID."
)
def get_hotspot_package(
    package_id: int,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Get hotspot package details.

    This endpoint:
    - Returns package details by ID
    - Only accessible by package owner (ISP)
    - Requires valid JWT access token
    """
    try:
        package = hotspot_service.get_package_by_id(
            db=db,
            package_id=package_id,
            isp_id=current_isp.id
        )

        return HotspotPackageResponse(
            id=package.id,
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            validity_minutes=package.validity_minutes,
            shared_users=package.shared_users,
            router_id=str(package.router_id),
            mikrotik_profile_name=package.mikrotik_profile_name,
            is_active=package.is_active,
            created_at=package.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve hotspot package: {str(e)}"
        )


@router.patch(
    "/packages/{package_id}/toggle",
    response_model=HotspotPackageResponse,
    summary="Toggle Hotspot Package",
    description="Enable or disable a hotspot package."
)
def toggle_hotspot_package(
    package_id: int,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Toggle hotspot package active status.

    This endpoint:
    - Toggles the is_active status of a package
    - Only accessible by package owner (ISP)
    - Requires valid JWT access token
    """
    try:
        package = hotspot_service.toggle_package(
            db=db,
            package_id=package_id,
            isp_id=current_isp.id
        )

        return HotspotPackageResponse(
            id=package.id,
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            validity_minutes=package.validity_minutes,
            shared_users=package.shared_users,
            router_id=str(package.router_id),
            mikrotik_profile_name=package.mikrotik_profile_name,
            is_active=package.is_active,
            created_at=package.created_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to toggle hotspot package: {str(e)}"
        )


# ==========================
# MAC Voucher Endpoints
# ==========================

@router.post(
    "/mac-vouchers",
    response_model=HotspotVoucherResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create MAC Voucher",
    description="Create a MAC-based hotspot voucher and assign to MikroTik router for auto-login."
)
def create_mac_voucher(
    request: HotspotVoucherCreate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Create a MAC-based hotspot voucher.

    This endpoint:
    - Creates a MAC voucher in the database
    - Assigns the MAC address to the hotspot profile on MikroTik
    - Enables auto-login for the device with the specified MAC address
    - Session timeout and speed limits are enforced by MikroTik
    - Requires valid JWT access token
    """
    try:
        voucher = hotspot_service.create_mac_voucher(
            db=db,
            isp_id=current_isp.id,
            voucher_data=request.model_dump()
        )

        return HotspotVoucherResponse(
            id=voucher.id,
            mac_address=voucher.mac_address,
            package_id=voucher.package_id,
            profile_name=voucher.profile_name,
            is_active=voucher.is_active,
            created_at=voucher.created_at.isoformat(),
            expires_at=voucher.expires_at.isoformat() if voucher.expires_at else None
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create MAC voucher: {str(e)}"
        )


@router.get(
    "/mac-vouchers",
    response_model=List[HotspotVoucherResponse],
    summary="List MAC Vouchers",
    description="Get list of MAC vouchers with optional filters."
)
def list_mac_vouchers(
    package_id: Optional[int] = Query(default=None, description="Filter by package ID"),
    active_only: bool = Query(default=False, description="Return only active vouchers"),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    List MAC vouchers.

    This endpoint:
    - Returns vouchers for the authenticated ISP
    - Supports filtering by package ID and active status
    - Requires valid JWT access token
    """
    try:
        vouchers = hotspot_service.get_mac_vouchers(
            db=db,
            isp_id=current_isp.id,
            package_id=package_id,
            active_only=active_only
        )

        return [
            HotspotVoucherResponse(
                id=v.id,
                mac_address=v.mac_address,
                package_id=v.package_id,
                profile_name=v.profile_name,
                is_active=v.is_active,
                created_at=v.created_at.isoformat(),
                expires_at=v.expires_at.isoformat() if v.expires_at else None
            )
            for v in vouchers
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve MAC vouchers: {str(e)}"
        )
