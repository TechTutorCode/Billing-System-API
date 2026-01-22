"""MikroTik service for hotspot operations."""

import logging
from typing import Optional

from fastapi import HTTPException, status

from app.routers.mikrotik_service import mikrotik_service as base_mikrotik_service

logger = logging.getLogger(__name__)


class HotspotMikroTikService:
    """Service for MikroTik hotspot operations."""

    @staticmethod
    def create_hotspot_profile(
        connection_dict,
        profile_name: str,
        download_speed: int,
        upload_speed: int,
        validity_minutes: int,
        shared_users: int = 1
    ) -> None:
        """
        Create Hotspot user profile on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name
            download_speed: Download speed in Kbps
            upload_speed: Upload speed in Kbps
            validity_minutes: Session timeout in minutes
            shared_users: Number of concurrent users (default: 1)

        Raises:
            HTTPException: If profile creation fails
        """
        try:
            api = connection_dict["api"]
            
            # Convert minutes to MikroTik format (e.g., 60 minutes = "1h", 1440 minutes = "1d")
            if validity_minutes < 60:
                session_timeout = f"{validity_minutes}m"
            elif validity_minutes < 1440:
                hours = validity_minutes // 60
                session_timeout = f"{hours}h"
            else:
                days = validity_minutes // 1440
                session_timeout = f"{days}d"
            
            # Convert Kbps to Mbps for rate-limit (MikroTik uses Mbps format)
            download_mbps = download_speed / 1000
            upload_mbps = upload_speed / 1000
            
            logger.info(
                f"Creating Hotspot profile '{profile_name}' with rate-limit {download_mbps}M/{upload_mbps}M, "
                f"session-timeout {session_timeout}, shared-users {shared_users}"
            )
            
            resource = api.get_resource("/ip/hotspot/user/profile")
            resource.add(
                name=profile_name,
                rate_limit=f"{download_mbps}M/{upload_mbps}M",
                session_timeout=session_timeout,
                shared_users=str(shared_users)
            )
            logger.info(f"Successfully created Hotspot profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to create Hotspot profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create Hotspot profile: {str(e)}"
            )

    @staticmethod
    def check_hotspot_profile_exists(
        connection_dict,
        profile_name: str
    ) -> bool:
        """
        Check if Hotspot profile exists on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name to check

        Returns:
            True if profile exists, False otherwise
        """
        try:
            api = connection_dict["api"]
            resource = api.get_resource("/ip/hotspot/user/profile")
            profiles = resource.get(name=profile_name)
            exists = len(profiles) > 0
            logger.info(f"Hotspot profile '{profile_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking Hotspot profile existence: {str(e)}")
            return False

    @staticmethod
    def update_hotspot_profile(
        connection_dict,
        profile_name: str,
        download_speed: int,
        upload_speed: int,
        validity_minutes: int,
        shared_users: int = 1
    ) -> None:
        """
        Update Hotspot user profile on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name
            download_speed: Download speed in Kbps
            upload_speed: Upload speed in Kbps
            validity_minutes: Session timeout in minutes
            shared_users: Number of concurrent users

        Raises:
            HTTPException: If profile update fails
        """
        try:
            api = connection_dict["api"]
            
            # Convert minutes to MikroTik format
            if validity_minutes < 60:
                session_timeout = f"{validity_minutes}m"
            elif validity_minutes < 1440:
                hours = validity_minutes // 60
                session_timeout = f"{hours}h"
            else:
                days = validity_minutes // 1440
                session_timeout = f"{days}d"
            
            # Convert Kbps to Mbps
            download_mbps = download_speed / 1000
            upload_mbps = upload_speed / 1000
            
            logger.info(
                f"Updating Hotspot profile '{profile_name}' with rate-limit {download_mbps}M/{upload_mbps}M, "
                f"session-timeout {session_timeout}, shared-users {shared_users}"
            )
            
            resource = api.get_resource("/ip/hotspot/user/profile")
            
            # Get existing profile
            profiles = resource.get(name=profile_name)
            if not profiles:
                logger.warning(f"Hotspot profile '{profile_name}' not found, creating new one")
                resource.add(
                    name=profile_name,
                    rate_limit=f"{download_mbps}M/{upload_mbps}M",
                    session_timeout=session_timeout,
                    shared_users=str(shared_users)
                )
            else:
                # Update existing profile
                resource.set(
                    id=profiles[0]["id"],
                    rate_limit=f"{download_mbps}M/{upload_mbps}M",
                    session_timeout=session_timeout,
                    shared_users=str(shared_users)
                )
            logger.info(f"Successfully updated Hotspot profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to update Hotspot profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update Hotspot profile: {str(e)}"
            )

    @staticmethod
    def remove_hotspot_profile(
        connection_dict,
        profile_name: str
    ) -> None:
        """
        Remove Hotspot profile from MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name to remove

        Raises:
            HTTPException: If profile removal fails
        """
        try:
            api = connection_dict["api"]
            resource = api.get_resource("/ip/hotspot/user/profile")
            
            # Check if profile exists
            profiles = resource.get(name=profile_name)
            if not profiles:
                logger.warning(f"Hotspot profile '{profile_name}' not found on router, skipping removal")
                return
            
            # Remove profile
            resource.remove(id=profiles[0]["id"])
            logger.info(f"Successfully removed Hotspot profile '{profile_name}' from router")
        except Exception as e:
            logger.error(f"Failed to remove Hotspot profile '{profile_name}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove Hotspot profile: {str(e)}"
            )

    @staticmethod
    def assign_mac_user(
        connection_dict,
        mac_address: str,
        profile_name: str
    ) -> None:
        """
        Assign MAC address to Hotspot user on MikroTik router.

        This creates a hotspot user entry that allows the MAC address to auto-login.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            mac_address: MAC address (format: XX:XX:XX:XX:XX:XX)
            profile_name: Hotspot profile name to assign

        Raises:
            HTTPException: If MAC user assignment fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Assigning MAC address '{mac_address}' to Hotspot profile '{profile_name}'")
            
            resource = api.get_resource("/ip/hotspot/user")
            
            # Check if MAC user already exists
            existing_users = resource.get(mac_address=mac_address)
            if existing_users:
                # Update existing user
                logger.info(f"MAC address '{mac_address}' already exists, updating profile")
                resource.set(
                    id=existing_users[0]["id"],
                    profile=profile_name,
                    disabled="false"
                )
            else:
                # Create new user
                resource.add(
                    mac_address=mac_address,
                    profile=profile_name,
                    disabled="false"
                )
            
            logger.info(f"Successfully assigned MAC address '{mac_address}' to profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to assign MAC user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to assign MAC user on router: {str(e)}"
            )

    @staticmethod
    def check_mac_user_exists(
        connection_dict,
        mac_address: str
    ) -> bool:
        """
        Check if MAC user exists on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            mac_address: MAC address to check

        Returns:
            True if MAC user exists, False otherwise
        """
        try:
            api = connection_dict["api"]
            resource = api.get_resource("/ip/hotspot/user")
            users = resource.get(mac_address=mac_address)
            exists = len(users) > 0
            logger.info(f"MAC user '{mac_address}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking MAC user existence: {str(e)}")
            return False

    @staticmethod
    def disable_mac_user(
        connection_dict,
        mac_address: str
    ) -> None:
        """
        Disable MAC user on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            mac_address: MAC address to disable

        Raises:
            HTTPException: If operation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Disabling MAC user '{mac_address}'")
            resource = api.get_resource("/ip/hotspot/user")
            users = resource.get(mac_address=mac_address)
            if not users:
                logger.warning(f"MAC user '{mac_address}' not found on router")
                return
            resource.set(id=users[0]["id"], disabled="true")
            logger.info(f"Successfully disabled MAC user '{mac_address}'")
        except Exception as e:
            logger.error(f"Failed to disable MAC user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to disable MAC user: {str(e)}"
            )

    @staticmethod
    def enable_mac_user(
        connection_dict,
        mac_address: str
    ) -> None:
        """
        Enable MAC user on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            mac_address: MAC address to enable

        Raises:
            HTTPException: If operation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Enabling MAC user '{mac_address}'")
            resource = api.get_resource("/ip/hotspot/user")
            users = resource.get(mac_address=mac_address)
            if not users:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"MAC user '{mac_address}' not found on router"
                )
            resource.set(id=users[0]["id"], disabled="false")
            logger.info(f"Successfully enabled MAC user '{mac_address}'")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to enable MAC user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enable MAC user: {str(e)}"
            )

    @staticmethod
    def remove_mac_user(
        connection_dict,
        mac_address: str
    ) -> None:
        """
        Remove MAC user from MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            mac_address: MAC address to remove

        Raises:
            HTTPException: If removal fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Removing MAC user '{mac_address}'")
            resource = api.get_resource("/ip/hotspot/user")
            users = resource.get(mac_address=mac_address)
            if not users:
                logger.warning(f"MAC user '{mac_address}' not found, skipping removal")
                return
            resource.remove(id=users[0]["id"])
            logger.info(f"Successfully removed MAC user '{mac_address}'")
        except Exception as e:
            logger.error(f"Failed to remove MAC user: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove MAC user: {str(e)}"
            )


# Global instance
hotspot_mikrotik_service = HotspotMikroTikService()
