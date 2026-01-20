"""Package business logic services."""

import logging
import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.packages.models import PackageType, ServicePackage
from app.packages.types import PackageType as PackageTypeEnum, ValidityUnit
from app.routers.models import Router
from app.routers.mikrotik_service import mikrotik_service
from app.routers.utils import verify_vpn_password

logger = logging.getLogger(__name__)


class PackageService:
    """Service for package-related operations."""

    @staticmethod
    def seed_package_types(db: Session) -> None:
        """
        Seed package types if they don't exist.
        Safe to call multiple times - does nothing if types already exist.
        """
        package_types_data = [
            {"name": PackageTypeEnum.PPPOE.value, "description": "PPPoE connection type"},
            {"name": PackageTypeEnum.STATIC.value, "description": "Static IP connection type"},
            {"name": PackageTypeEnum.HOTSPOT.value, "description": "Hotspot connection type"},
        ]

        for type_data in package_types_data:
            existing = db.query(PackageType).filter(PackageType.name == type_data["name"]).first()
            if not existing:
                package_type = PackageType(**type_data)
                db.add(package_type)

        db.commit()

    @staticmethod
    def get_all_package_types(db: Session) -> List[PackageType]:
        """
        Get all package types.

        Args:
            db: Database session

        Returns:
            List of PackageType instances
        """
        return db.query(PackageType).order_by(PackageType.name).all()

    @staticmethod
    def get_package_type_by_id(db: Session, package_type_id: UUID) -> PackageType:
        """
        Get package type by ID.

        Args:
            db: Database session
            package_type_id: Package type ID

        Returns:
            PackageType instance

        Raises:
            HTTPException: If package type not found
        """
        package_type = db.query(PackageType).filter(PackageType.id == package_type_id).first()
        if not package_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package type not found"
            )
        return package_type

    @staticmethod
    def create_package(
        db: Session,
        isp_id: UUID,
        package_data: dict
    ) -> ServicePackage:
        """
        Create a new service package.

        Args:
            db: Database session
            isp_id: ISP ID (for router ownership verification)
            package_data: Package data dictionary

        Returns:
            ServicePackage instance

        Raises:
            HTTPException: If validation fails
        """
        router_id = package_data["router_id"]
        package_type_id = package_data["package_type_id"]
        name = package_data["name"]

        # Verify router exists and belongs to ISP
        router = db.query(Router).filter(
            Router.id == router_id,
            Router.isp_id == isp_id,
            Router.is_active == True
        ).first()

        if not router:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Router not found or does not belong to you"
            )

        # Verify package type exists
        package_type = PackageService.get_package_type_by_id(db, package_type_id)

        # Check for duplicate (router_id, name, package_type_id)
        existing = db.query(ServicePackage).filter(
            ServicePackage.router_id == router_id,
            ServicePackage.name == name,
            ServicePackage.package_type_id == package_type_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Package with name '{name}' and type '{package_type.name}' already exists for this router"
            )

        # Create package
        service_package = ServicePackage(**package_data)
        db.add(service_package)
        db.commit()
        db.refresh(service_package)

        return service_package

    @staticmethod
    def get_packages_by_router(
        db: Session,
        router_id: UUID,
        isp_id: UUID,
        active_only: bool = True
    ) -> List[ServicePackage]:
        """
        Get packages for a specific router.

        Args:
            db: Database session
            router_id: Router ID
            isp_id: ISP ID (for router ownership verification)
            active_only: If True, return only active packages

        Returns:
            List of ServicePackage instances

        Raises:
            HTTPException: If router not found or doesn't belong to ISP
        """
        # Verify router exists and belongs to ISP
        router = db.query(Router).filter(
            Router.id == router_id,
            Router.isp_id == isp_id,
            Router.is_active == True
        ).first()

        if not router:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Router not found or does not belong to you"
            )

        query = db.query(ServicePackage).filter(ServicePackage.router_id == router_id)

        if active_only:
            query = query.filter(ServicePackage.is_active == True)

        return query.order_by(ServicePackage.created_at.desc()).all()

    @staticmethod
    def get_package_by_id(
        db: Session,
        package_id: UUID,
        isp_id: UUID
    ) -> ServicePackage:
        """
        Get package by ID.

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            ServicePackage instance

        Raises:
            HTTPException: If package not found or doesn't belong to ISP
        """
        package = (
            db.query(ServicePackage)
            .join(Router)
            .filter(
                ServicePackage.id == package_id,
                Router.isp_id == isp_id
            )
            .first()
        )

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found or does not belong to you"
            )

        return package

    @staticmethod
    def update_package(
        db: Session,
        package_id: UUID,
        isp_id: UUID,
        package_data: dict
    ) -> ServicePackage:
        """
        Update a service package.

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)
            package_data: Package data dictionary (only provided fields)

        Returns:
            Updated ServicePackage instance

        Raises:
            HTTPException: If package not found or validation fails
        """
        package = PackageService.get_package_by_id(db, package_id, isp_id)

        # Update fields
        for key, value in package_data.items():
            if value is not None:
                setattr(package, key, value)

        package.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(package)

        return package

    @staticmethod
    def disable_package(
        db: Session,
        package_id: UUID,
        isp_id: UUID
    ) -> ServicePackage:
        """
        Disable a service package (soft delete).

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            Updated ServicePackage instance

        Raises:
            HTTPException: If package not found
        """
        package = PackageService.get_package_by_id(db, package_id, isp_id)

        package.is_active = False
        package.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(package)

        return package

    @staticmethod
    def enable_package(
        db: Session,
        package_id: UUID,
        isp_id: UUID
    ) -> ServicePackage:
        """
        Enable a service package.

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            Updated ServicePackage instance

        Raises:
            HTTPException: If package not found
        """
        package = PackageService.get_package_by_id(db, package_id, isp_id)

        package.is_active = True
        package.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(package)

        return package

    @staticmethod
    def convert_validity_to_mikrotik_format(validity_value: int, validity_unit: str) -> str:
        """
        Convert validity to MikroTik format.

        Args:
            validity_value: Validity value (e.g., 30)
            validity_unit: Validity unit (minutes, hours, days)

        Returns:
            MikroTik format string (e.g., "30d", "12h", "90m")

        Raises:
            HTTPException: If validity unit is invalid
        """
        if validity_unit == ValidityUnit.MINUTES.value:
            return f"{validity_value}m"
        elif validity_unit == ValidityUnit.HOURS.value:
            return f"{validity_value}h"
        elif validity_unit == ValidityUnit.DAYS.value:
            return f"{validity_value}d"
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid validity unit: {validity_unit}"
            )

    @staticmethod
    def sync_package_to_mikrotik(
        db: Session,
        package_id: UUID,
        isp_id: UUID,
        api_password: Optional[str] = None
    ) -> ServicePackage:
        """
        Sync package to MikroTik router.

        This function:
        - Loads package and router
        - Validates router is active and has VPN IP
        - Connects to MikroTik via API
        - Checks if profile already exists (idempotent)
        - Creates profile if missing
        - Updates package sync status

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)
            api_password: MikroTik API password (optional, falls back to stored password)

        Returns:
            Updated ServicePackage instance

        Raises:
            HTTPException: If validation fails or sync fails
        """
        # Get package and verify ownership
        package = PackageService.get_package_by_id(db, package_id, isp_id)

        # Load router with package type
        router = (
            db.query(Router)
            .filter(Router.id == package.router_id)
            .first()
        )

        if not router:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Router not found"
            )

        # Validate router is active
        if not router.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router is not active"
            )

        # Validate router has VPN IP
        if not router.vpn_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router VPN IP not available. Router must be connected via VPN."
            )

        # Get package type name
        package_type = db.query(PackageType).filter(PackageType.id == package.package_type_id).first()
        if not package_type:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package type not found"
            )

        package_type_name = package_type.name.lower()

        # Validate package type
        if package_type_name not in ["pppoe", "hotspot", "static"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid package type for MikroTik sync: {package_type_name}"
            )

        # Generate profile name
        profile_name = f"pkg_{str(package.id).replace('-', '')[:12]}"

        # Connect to MikroTik
        api_username = router.mikrotik_api_username or "admin"
        
        # Get API password from database (stored in plain text)
        if router.mikrotik_api_password:
            api_password_plain = router.mikrotik_api_password
        elif api_password:
            # Fallback to provided password if not stored (for backward compatibility)
            api_password_plain = api_password
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password not configured. Please configure it in router settings."
            )

        connection = None
        try:
            # Connect to MikroTik
            connection = mikrotik_service.connect(
                host=router.vpn_ip,
                username=api_username,
                password=api_password_plain,
                port=router.api_port
            )

            # Check if profile already exists (idempotent)
            if mikrotik_service.check_profile_exists(connection, profile_name, package_type_name):
                logger.info(f"Profile '{profile_name}' already exists on router, skipping creation")
            else:
                # Convert validity to MikroTik format
                session_timeout = PackageService.convert_validity_to_mikrotik_format(
                    package.validity_value,
                    package.validity_unit
                )

                # Create profile based on package type
                if package_type_name == "pppoe":
                    mikrotik_service.create_pppoe_profile(
                        connection_dict=connection,
                        profile_name=profile_name,
                        download_speed=package.download_speed,
                        upload_speed=package.upload_speed,
                        session_timeout=session_timeout
                    )
                elif package_type_name == "hotspot":
                    mikrotik_service.create_hotspot_profile(
                        connection_dict=connection,
                        profile_name=profile_name,
                        download_speed=package.download_speed,
                        upload_speed=package.upload_speed
                    )
                elif package_type_name == "static":
                    mikrotik_service.create_static_queue(
                        connection_dict=connection,
                        queue_name=profile_name,
                        download_speed=package.download_speed,
                        upload_speed=package.upload_speed
                    )

                logger.info(f"Successfully created profile '{profile_name}' on router")

            # Update package sync status
            package.mikrotik_profile_name = profile_name
            package.mikrotik_synced = True
            package.mikrotik_synced_at = datetime.now(timezone.utc)
            package.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(package)

            return package

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to sync package to MikroTik: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to sync package to MikroTik: {str(e)}"
            )
        finally:
            # Close connection pool if it was opened
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")


# Global instance
package_service = PackageService()

