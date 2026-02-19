"""Router business logic services."""

import secrets
import uuid
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.isps.models import ISPDetails
from app.routers.mikrotik_service import mikrotik_service
from app.routers.models import Router, RouterStatus
from app.routers.utils import (
    encrypt_vpn_password,
    generate_mikrotik_openvpn_config,
    generate_router_password,
    generate_vpn_username,
)
from app.routers.vpn_service import vpn_service


class RouterService:
    """Service for router operations."""

    @staticmethod
    def create_router(
        db: Session,
        isp: ISPDetails,
        name: str,
        openvpn_server_ip: str,
        openvpn_server_port: int,
        mikrotik_api_username: Optional[str] = "admin",
        mikrotik_api_password: Optional[str] = None
    ) -> tuple[Router, str]:
        """
        Create a new router and VPN user.

        Args:
            db: Database session
            isp: ISPDetails instance
            name: Router name
            openvpn_server_ip: OpenVPN server IP address
            openvpn_server_port: OpenVPN server port

        Returns:
            Tuple of (Router instance, plain text password for config generation)

        Raises:
            HTTPException: If router creation fails
        """
        # Generate VPN credentials
        router_id_str = str(uuid.uuid4())
        vpn_username = generate_vpn_username(router_id_str)
        vpn_password = generate_router_password()
        vpn_password_encrypted = encrypt_vpn_password(vpn_password)

        # Generate RADIUS secret for this router (used in FreeRADIUS nas table and MikroTik RADIUS client)
        radius_secret = secrets.token_hex(16)

        # Create router record first (to get the ID)
        router = Router(
            isp_id=isp.id,
            name=name,
            vpn_username=vpn_username,
            vpn_password_encrypted=vpn_password_encrypted,
            api_port=8728,
            mikrotik_api_username=mikrotik_api_username or "admin",
            mikrotik_api_password=mikrotik_api_password,
            status=RouterStatus.PENDING.value,
            is_active=True,
            radius_secret=radius_secret,
            radius_configured=False,
        )
        db.add(router)
        db.flush()  # Flush to get the ID

        # Update username with actual router ID
        router.vpn_username = generate_vpn_username(str(router.id))
        db.flush()

        try:
            # Create VPN user
            vpn_service.add_vpn_user(router.vpn_username, vpn_password)
        except HTTPException:
            # Rollback router creation if VPN user creation fails
            db.rollback()
            raise

        # Commit router creation
        db.commit()
        db.refresh(router)

        return router, vpn_password

    @staticmethod
    def get_router_config(
        router: Router,
        openvpn_server_ip: str,
        openvpn_server_port: int,
        vpn_password: Optional[str] = None
    ) -> str:
        """
        Get MikroTik OpenVPN client configuration.

        Args:
            router: Router instance
            openvpn_server_ip: OpenVPN server IP address
            openvpn_server_port: OpenVPN server port
            vpn_password: Plain text password (only available during creation)

        Returns:
            RouterOS CLI configuration string

        Raises:
            HTTPException: If password is not available and router exists
        """
        if not vpn_password:
            # Password should never be returned in plaintext after creation
            # This should only be called during creation
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="VPN password cannot be retrieved after creation. Please use the config provided during router creation."
            )

        return generate_mikrotik_openvpn_config(
            server_ip=openvpn_server_ip,
            server_port=openvpn_server_port,
            username=router.vpn_username,
            password=vpn_password,
            protocol="tcp",
            auth="sha1",
            cipher="aes128"
        )

    @staticmethod
    def delete_router(db: Session, router: Router) -> bool:
        """
        Delete router and remove VPN user.

        Args:
            db: Database session
            router: Router instance

        Returns:
            True if deletion successful

        Raises:
            HTTPException: If deletion fails
        """
        try:
            # Delete VPN user
            vpn_service.delete_vpn_user(router.vpn_username)
        except HTTPException as e:
            # Log but continue with router deletion
            import logging
            logger = logging.getLogger(__name__)
            logger.warning(f"Failed to delete VPN user {router.vpn_username}: {str(e)}")

        # Mark router as inactive instead of deleting (for audit trail)
        router.is_active = False
        db.commit()

        return True

    @staticmethod
    def update_router(
        db: Session,
        router: Router,
        name: Optional[str] = None,
        api_port: Optional[int] = None,
        mikrotik_api_username: Optional[str] = None,
        mikrotik_api_password: Optional[str] = None
    ) -> Router:
        """
        Update router information.

        Args:
            db: Database session
            router: Router instance
            name: Router name
            api_port: MikroTik API port
            mikrotik_api_username: MikroTik API username
            mikrotik_api_password: MikroTik API password (stored in plain text)

        Returns:
            Updated router instance

        Raises:
            HTTPException: If update fails
        """
        if name is not None:
            router.name = name

        if api_port is not None:
            router.api_port = api_port

        if mikrotik_api_username is not None:
            router.mikrotik_api_username = mikrotik_api_username

        if mikrotik_api_password is not None:
            # Store password in plain text (needed for API connections)
            router.mikrotik_api_password = mikrotik_api_password

        db.commit()
        db.refresh(router)

        return router

    @staticmethod
    def update_router_status(
        db: Session,
        router: Router,
        vpn_ip: Optional[str] = None,
        status: Optional[RouterStatus] = None,
        update_last_seen: bool = True
    ) -> Router:
        """
        Update router status and VPN IP.

        Args:
            db: Database session
            router: Router instance
            vpn_ip: VPN IP address
            status: Router status

        Returns:
            Updated router instance
        """
        if vpn_ip is not None:
            router.vpn_ip = vpn_ip

        if status is not None:
            router.status = status.value

        # Always update last_seen to current time when router is detected
        if update_last_seen:
            from datetime import datetime, timezone
            router.last_seen = datetime.now(timezone.utc)

        db.commit()
        db.refresh(router)

        return router


# Global instance
router_service = RouterService()

