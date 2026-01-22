"""Hotspot business logic services."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.hotspot.models import HotspotPackage, HotspotVoucher
from app.hotspot.mikrotik_service import hotspot_mikrotik_service
from app.routers.models import Router
from app.routers.mikrotik_service import mikrotik_service

logger = logging.getLogger(__name__)


class HotspotService:
    """Service for hotspot-related operations."""

    @staticmethod
    def create_package(
        db: Session,
        isp_id: UUID,
        package_data: dict,
        api_password: Optional[str] = None
    ) -> HotspotPackage:
        """
        Create a new hotspot package and sync to MikroTik.

        Args:
            db: Database session
            isp_id: ISP ID (for router ownership verification)
            package_data: Package data dictionary
            api_password: MikroTik API password (optional, falls back to stored password)

        Returns:
            HotspotPackage instance

        Raises:
            HTTPException: If validation fails or MikroTik sync fails
        """
        router_id = UUID(package_data["router_id"])
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

        # Check for duplicate package name on same router
        existing = db.query(HotspotPackage).filter(
            HotspotPackage.router_id == router_id,
            HotspotPackage.name == name
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Hotspot package with name '{name}' already exists for this router"
            )

        # Validate router has VPN IP
        if not router.vpn_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router VPN IP not available. Router must be connected via VPN."
            )

        # Get API credentials
        api_username = router.mikrotik_api_username or "admin"
        if router.mikrotik_api_password:
            api_password_plain = router.mikrotik_api_password
        elif api_password:
            api_password_plain = api_password
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password not configured. Please configure it in router settings."
            )

        # Generate profile name
        # Use a simple format: hotspot_pkg_{package_id} (will be updated after creation)
        profile_name = f"hotspot_pkg_{name.lower().replace(' ', '_')}"

        connection = None
        try:
            # Connect to MikroTik
            connection = mikrotik_service.connect(
                host=router.vpn_ip,
                username=api_username,
                password=api_password_plain,
                port=router.api_port
            )

            # Check if profile already exists
            if hotspot_mikrotik_service.check_hotspot_profile_exists(connection, profile_name):
                # Append timestamp to make it unique
                profile_name = f"{profile_name}_{int(datetime.now(timezone.utc).timestamp())}"

            # Create profile on MikroTik
            hotspot_mikrotik_service.create_hotspot_profile(
                connection_dict=connection,
                profile_name=profile_name,
                download_speed=package_data["download_speed"],
                upload_speed=package_data["upload_speed"],
                validity_minutes=package_data["validity_minutes"],
                shared_users=package_data.get("shared_users", 1)
            )

            # Create package in database
            hotspot_package = HotspotPackage(
                name=name,
                download_speed=package_data["download_speed"],
                upload_speed=package_data["upload_speed"],
                validity_minutes=package_data["validity_minutes"],
                shared_users=package_data.get("shared_users", 1),
                router_id=router_id,
                mikrotik_profile_name=profile_name,
                is_active=True
            )
            db.add(hotspot_package)
            db.commit()
            db.refresh(hotspot_package)

            logger.info(f"Created hotspot package {hotspot_package.id} with profile '{profile_name}'")
            return hotspot_package

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create hotspot package: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create hotspot package: {str(e)}"
            )
        finally:
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")

    @staticmethod
    def get_packages(
        db: Session,
        isp_id: UUID,
        active_only: bool = True
    ) -> List[HotspotPackage]:
        """
        Get hotspot packages for an ISP.

        Args:
            db: Database session
            isp_id: ISP ID
            active_only: If True, return only active packages

        Returns:
            List of HotspotPackage instances
        """
        query = (
            db.query(HotspotPackage)
            .join(Router)
            .filter(Router.isp_id == isp_id)
        )

        if active_only:
            query = query.filter(HotspotPackage.is_active == True)

        return query.order_by(HotspotPackage.created_at.desc()).all()

    @staticmethod
    def get_package_by_id(
        db: Session,
        package_id: int,
        isp_id: UUID
    ) -> HotspotPackage:
        """
        Get hotspot package by ID.

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            HotspotPackage instance

        Raises:
            HTTPException: If package not found or doesn't belong to ISP
        """
        package = (
            db.query(HotspotPackage)
            .join(Router)
            .filter(
                HotspotPackage.id == package_id,
                Router.isp_id == isp_id
            )
            .first()
        )

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotspot package not found or does not belong to you"
            )

        return package

    @staticmethod
    def toggle_package(
        db: Session,
        package_id: int,
        isp_id: UUID
    ) -> HotspotPackage:
        """
        Toggle hotspot package active status.

        Args:
            db: Database session
            package_id: Package ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            Updated HotspotPackage instance

        Raises:
            HTTPException: If package not found
        """
        package = HotspotService.get_package_by_id(db, package_id, isp_id)

        package.is_active = not package.is_active
        db.commit()
        db.refresh(package)

        logger.info(f"Toggled hotspot package {package_id} to is_active={package.is_active}")
        return package

    @staticmethod
    def create_mac_voucher(
        db: Session,
        isp_id: UUID,
        voucher_data: dict,
        api_password: Optional[str] = None
    ) -> HotspotVoucher:
        """
        Create a MAC-based hotspot voucher and assign to MikroTik.

        Args:
            db: Database session
            isp_id: ISP ID (for package ownership verification)
            voucher_data: Voucher data dictionary
            api_password: MikroTik API password (optional, falls back to stored password)

        Returns:
            HotspotVoucher instance

        Raises:
            HTTPException: If validation fails or MikroTik assignment fails
        """
        mac_address = voucher_data["mac_address"]
        package_id = voucher_data["package_id"]

        # Get package and verify ownership
        package = (
            db.query(HotspotPackage)
            .join(Router)
            .filter(
                HotspotPackage.id == package_id,
                Router.isp_id == isp_id
            )
            .first()
        )

        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Hotspot package not found or does not belong to you"
            )

        if not package.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Cannot create voucher for inactive package"
            )

        if not package.mikrotik_profile_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Package does not have a MikroTik profile. Please sync the package first."
            )

        # Check for duplicate MAC address in same package
        existing = db.query(HotspotVoucher).filter(
            HotspotVoucher.mac_address == mac_address,
            HotspotVoucher.package_id == package_id
        ).first()

        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"MAC address '{mac_address}' already exists for this package"
            )

        # Load router
        router = db.query(Router).filter(Router.id == package.router_id).first()
        if not router or not router.vpn_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router not available"
            )

        # Get API credentials
        api_username = router.mikrotik_api_username or "admin"
        if router.mikrotik_api_password:
            api_password_plain = router.mikrotik_api_password
        elif api_password:
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

            # Assign MAC user to profile on MikroTik
            hotspot_mikrotik_service.assign_mac_user(
                connection_dict=connection,
                mac_address=mac_address,
                profile_name=package.mikrotik_profile_name
            )

            # Create voucher in database
            voucher = HotspotVoucher(
                mac_address=mac_address,
                package_id=package_id,
                profile_name=package.mikrotik_profile_name,
                is_active=True,
                expires_at=voucher_data.get("expires_at")
            )
            db.add(voucher)
            db.commit()
            db.refresh(voucher)

            logger.info(f"Created hotspot voucher {voucher.id} for MAC {mac_address}")
            return voucher

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to create MAC voucher: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create MAC voucher: {str(e)}"
            )
        finally:
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")

    @staticmethod
    def get_mac_vouchers(
        db: Session,
        isp_id: UUID,
        package_id: Optional[int] = None,
        active_only: bool = False
    ) -> List[HotspotVoucher]:
        """
        Get MAC vouchers for an ISP.

        Args:
            db: Database session
            isp_id: ISP ID
            package_id: Optional package ID filter
            active_only: If True, return only active vouchers

        Returns:
            List of HotspotVoucher instances
        """
        query = (
            db.query(HotspotVoucher)
            .join(HotspotPackage)
            .join(Router)
            .filter(Router.isp_id == isp_id)
        )

        if package_id:
            query = query.filter(HotspotVoucher.package_id == package_id)

        if active_only:
            query = query.filter(HotspotVoucher.is_active == True)

        return query.order_by(HotspotVoucher.created_at.desc()).all()

    @staticmethod
    def expire_vouchers(db: Session) -> int:
        """
        Expire vouchers that have passed their expires_at date.

        This should be called by a background task.

        Args:
            db: Database session

        Returns:
            Number of vouchers expired
        """
        now = datetime.now(timezone.utc)

        # Find vouchers that should be expired
        expired_vouchers = (
            db.query(HotspotVoucher)
            .filter(
                HotspotVoucher.is_active == True,
                HotspotVoucher.expires_at.isnot(None),
                HotspotVoucher.expires_at < now
            )
            .all()
        )

        expired_count = 0
        for voucher in expired_vouchers:
            try:
                # Load package and router
                package = db.query(HotspotPackage).filter(HotspotPackage.id == voucher.package_id).first()
                if not package:
                    continue

                router = db.query(Router).filter(Router.id == package.router_id).first()
                if router and router.vpn_ip and router.mikrotik_api_password:
                    # Get API credentials
                    api_username = router.mikrotik_api_username or "admin"
                    api_password_plain = router.mikrotik_api_password

                    connection = None
                    try:
                        # Connect to MikroTik
                        connection = mikrotik_service.connect(
                            host=router.vpn_ip,
                            username=api_username,
                            password=api_password_plain,
                            port=router.api_port
                        )

                        # Disable MAC user on MikroTik
                        hotspot_mikrotik_service.disable_mac_user(
                            connection_dict=connection,
                            mac_address=voucher.mac_address
                        )
                    except Exception as e:
                        logger.error(f"Failed to disable MAC user {voucher.mac_address} on router: {str(e)}")
                        # Continue to mark as expired even if router operation fails
                    finally:
                        if connection:
                            try:
                                connection_pool = connection.get("pool")
                                if connection_pool:
                                    connection_pool.disconnect()
                            except Exception:
                                pass

                # Mark as inactive
                voucher.is_active = False
                expired_count += 1

            except Exception as e:
                logger.error(f"Error expiring voucher {voucher.id}: {str(e)}")
                continue

        if expired_count > 0:
            db.commit()
            logger.info(f"Expired {expired_count} hotspot voucher(s)")

        return expired_count


# Global instance
hotspot_service = HotspotService()
