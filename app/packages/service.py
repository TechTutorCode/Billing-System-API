"""Package business logic services."""

import uuid
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.packages.models import PackageType, ServicePackage
from app.packages.types import PackageType as PackageTypeEnum
from app.routers.models import Router


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


# Global instance
package_service = PackageService()

