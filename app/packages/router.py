"""Package API routes."""

from typing import List
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_isp
from app.database import get_db
from app.isps.models import ISPDetails
from app.packages.schemas import (
    PackageCreate,
    PackageResponse,
    PackageSyncRequest,
    PackageSyncResponse,
    PackageTypeResponse,
    PackageUpdate,
)
from app.packages.service import package_service

router = APIRouter(prefix="/packages", tags=["Packages"])


@router.get(
    "/package-types",
    response_model=List[PackageTypeResponse],
    summary="List Package Types",
    description="Get list of all available package types (pppoe, static, hotspot)."
)
def list_package_types(db: Session = Depends(get_db)):
    """
    List all package types.

    This endpoint:
    - Returns all package types
    - Read-only endpoint
    - No authentication required (can be made public)
    """
    try:
        package_types = package_service.get_all_package_types(db=db)
        return [
            PackageTypeResponse(
                id=str(pt.id),
                name=pt.name,
                description=pt.description,
                created_at=pt.created_at.isoformat() if pt.created_at else ""
            )
            for pt in package_types
        ]
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve package types: {str(e)}"
        )


@router.post(
    "",
    response_model=PackageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Package",
    description="Create a new service package for a router."
)
def create_package(
    request: PackageCreate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Create a new service package.

    This endpoint:
    - Creates a package for a router
    - Requires valid JWT access token
    - Validates router ownership
    - Prevents duplicate packages per router + type
    """
    try:
        package_data = request.model_dump()
        package = package_service.create_package(
            db=db,
            isp_id=current_isp.id,
            package_data=package_data
        )

        # Load package type relationship
        db.refresh(package)

        return PackageResponse(
            id=str(package.id),
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            price=str(package.price),
            validity_value=package.validity_value,
            validity_unit=package.validity_unit,
            data_limit_gb=package.data_limit_gb,
            router_id=str(package.router_id),
            package_type_id=str(package.package_type_id),
            package_type=PackageTypeResponse(
                id=str(package.package_type.id),
                name=package.package_type.name,
                description=package.package_type.description,
                created_at=package.package_type.created_at.isoformat()
            ),
            mikrotik_profile=package.mikrotik_profile,
            mikrotik_profile_name=package.mikrotik_profile_name,
            mikrotik_synced=package.mikrotik_synced,
            mikrotik_synced_at=package.mikrotik_synced_at.isoformat() if package.mikrotik_synced_at else None,
            is_active=package.is_active,
            created_at=package.created_at.isoformat(),
            updated_at=package.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create package: {str(e)}"
        )


@router.get(
    "/routers/{router_id}/packages",
    response_model=List[PackageResponse],
    summary="List Packages by Router",
    description="Get list of all packages (active and inactive) for a specific router."
)
def list_packages_by_router(
    router_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    List packages for a specific router.

    This endpoint:
    - Returns all packages (active and inactive) for the router
    - Requires valid JWT access token
    - Validates router ownership
    """
    try:
        router_uuid = UUID(router_id)
        packages = package_service.get_packages_by_router(
            db=db,
            router_id=router_uuid,
            isp_id=current_isp.id,
            active_only=False
        )

        package_responses = []
        for package in packages:
            package_responses.append(
                PackageResponse(
                    id=str(package.id),
                    name=package.name,
                    download_speed=package.download_speed,
                    upload_speed=package.upload_speed,
                    price=str(package.price),
                    validity_value=package.validity_value,
                    validity_unit=package.validity_unit,
                    data_limit_gb=package.data_limit_gb,
                    router_id=str(package.router_id),
                    package_type_id=str(package.package_type_id),
                    package_type=PackageTypeResponse(
                        id=str(package.package_type.id),
                        name=package.package_type.name,
                        description=package.package_type.description,
                        created_at=package.package_type.created_at.isoformat()
                    ),
                    mikrotik_profile=package.mikrotik_profile,
                    mikrotik_profile_name=package.mikrotik_profile_name,
                    mikrotik_synced=package.mikrotik_synced,
                    mikrotik_synced_at=package.mikrotik_synced_at.isoformat() if package.mikrotik_synced_at else None,
                    is_active=package.is_active,
                    created_at=package.created_at.isoformat(),
                    updated_at=package.updated_at.isoformat()
                )
            )

        return package_responses
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
            detail=f"Failed to retrieve packages: {str(e)}"
        )


@router.put(
    "/{package_id}",
    response_model=PackageResponse,
    summary="Update Package",
    description="Update an existing service package."
)
def update_package(
    package_id: str,
    request: PackageUpdate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Update a service package.

    This endpoint:
    - Updates package fields (all optional)
    - Requires valid JWT access token
    - Validates package ownership
    """
    try:
        package_uuid = UUID(package_id)
        package_data = request.model_dump(exclude_unset=True)

        package = package_service.update_package(
            db=db,
            package_id=package_uuid,
            isp_id=current_isp.id,
            package_data=package_data
        )

        # Load package type relationship
        db.refresh(package)

        return PackageResponse(
            id=str(package.id),
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            price=str(package.price),
            validity_value=package.validity_value,
            validity_unit=package.validity_unit,
            data_limit_gb=package.data_limit_gb,
            router_id=str(package.router_id),
            package_type_id=str(package.package_type_id),
            package_type=PackageTypeResponse(
                id=str(package.package_type.id),
                name=package.package_type.name,
                description=package.package_type.description,
                created_at=package.package_type.created_at.isoformat()
            ),
            mikrotik_profile=package.mikrotik_profile,
            mikrotik_profile_name=package.mikrotik_profile_name,
            mikrotik_synced=package.mikrotik_synced,
            mikrotik_synced_at=package.mikrotik_synced_at.isoformat() if package.mikrotik_synced_at else None,
            is_active=package.is_active,
            created_at=package.created_at.isoformat(),
            updated_at=package.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update package: {str(e)}"
        )


@router.patch(
    "/packages/{package_id}/disable",
    response_model=PackageResponse,
    summary="Disable Package",
    description="Disable a service package (soft delete)."
)
def disable_package(
    package_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Disable a service package.

    This endpoint:
    - Sets is_active=False (soft delete)
    - Requires valid JWT access token
    - Validates package ownership
    """
    try:
        package_uuid = UUID(package_id)
        package = package_service.disable_package(
            db=db,
            package_id=package_uuid,
            isp_id=current_isp.id
        )

        # Load package type relationship
        db.refresh(package)

        return PackageResponse(
            id=str(package.id),
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            price=str(package.price),
            validity_value=package.validity_value,
            validity_unit=package.validity_unit,
            data_limit_gb=package.data_limit_gb,
            router_id=str(package.router_id),
            package_type_id=str(package.package_type_id),
            package_type=PackageTypeResponse(
                id=str(package.package_type.id),
                name=package.package_type.name,
                description=package.package_type.description,
                created_at=package.package_type.created_at.isoformat()
            ),
            mikrotik_profile=package.mikrotik_profile,
            mikrotik_profile_name=package.mikrotik_profile_name,
            mikrotik_synced=package.mikrotik_synced,
            mikrotik_synced_at=package.mikrotik_synced_at.isoformat() if package.mikrotik_synced_at else None,
            is_active=package.is_active,
            created_at=package.created_at.isoformat(),
            updated_at=package.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to disable package: {str(e)}"
        )


@router.patch(
    "/{package_id}/enable",
    response_model=PackageResponse,
    summary="Enable Package",
    description="Enable a disabled service package."
)
def enable_package(
    package_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Enable a service package.

    This endpoint:
    - Sets is_active=True
    - Requires valid JWT access token
    - Validates package ownership
    """
    try:
        package_uuid = UUID(package_id)
        package = package_service.enable_package(
            db=db,
            package_id=package_uuid,
            isp_id=current_isp.id
        )

        # Load package type relationship
        db.refresh(package)

        return PackageResponse(
            id=str(package.id),
            name=package.name,
            download_speed=package.download_speed,
            upload_speed=package.upload_speed,
            price=str(package.price),
            validity_value=package.validity_value,
            validity_unit=package.validity_unit,
            data_limit_gb=package.data_limit_gb,
            router_id=str(package.router_id),
            package_type_id=str(package.package_type_id),
            package_type=PackageTypeResponse(
                id=str(package.package_type.id),
                name=package.package_type.name,
                description=package.package_type.description,
                created_at=package.package_type.created_at.isoformat()
            ),
            mikrotik_profile=package.mikrotik_profile,
            mikrotik_profile_name=package.mikrotik_profile_name,
            mikrotik_synced=package.mikrotik_synced,
            mikrotik_synced_at=package.mikrotik_synced_at.isoformat() if package.mikrotik_synced_at else None,
            is_active=package.is_active,
            created_at=package.created_at.isoformat(),
            updated_at=package.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to enable package: {str(e)}"
        )


@router.post(
    "/{package_id}/sync",
    response_model=PackageSyncResponse,
    status_code=status.HTTP_200_OK,
    summary="Sync Package to MikroTik",
    description="Sync package to MikroTik router. Creates profile if it doesn't exist (idempotent)."
)
def sync_package_to_mikrotik(
    package_id: str,
    request: PackageSyncRequest,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Sync package to MikroTik router.

    This endpoint:
    - Connects to the router's MikroTik API
    - Checks if profile already exists (idempotent)
    - Creates profile if missing
    - Updates package sync status

    Requires:
    - Valid JWT access token
    - Package must belong to ISP's router
    - Router must be active and have VPN IP
    - MikroTik API password (if not stored)
    """
    try:
        package_uuid = UUID(package_id)
        package = package_service.sync_package_to_mikrotik(
            db=db,
            package_id=package_uuid,
            isp_id=current_isp.id,
            api_password=request.api_password
        )

        # Get router name
        from app.routers.models import Router
        router = db.query(Router).filter(Router.id == package.router_id).first()
        router_name = router.name if router else "Unknown"

        return PackageSyncResponse(
            status="success",
            profile=package.mikrotik_profile_name or "",
            router=router_name
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid package ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to sync package to MikroTik: {str(e)}"
        )

