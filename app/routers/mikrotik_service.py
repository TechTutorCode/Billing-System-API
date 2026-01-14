"""MikroTik API service for testing router connectivity and executing commands."""

import logging
import socket
from typing import Dict, List, Optional, Any

from fastapi import HTTPException, status
from routeros_api.api import connect

logger = logging.getLogger(__name__)


class MikroTikService:
    """Service for MikroTik API operations."""

    @staticmethod
    def test_api_connection(vpn_ip: str, api_port: int = 8728, timeout: int = 5) -> bool:
        """
        Test MikroTik API connection over VPN IP.

        Args:
            vpn_ip: Router VPN IP address
            api_port: MikroTik API port (default 8728)
            timeout: Connection timeout in seconds

        Returns:
            True if API is accessible, False otherwise
        """
        try:
            # Create socket connection to test if port is open
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(timeout)
            
            result = sock.connect_ex((vpn_ip, api_port))
            sock.close()
            
            if result == 0:
                logger.info(f"MikroTik API accessible at {vpn_ip}:{api_port}")
                return True
            else:
                logger.debug(f"MikroTik API not accessible at {vpn_ip}:{api_port}")
                return False

        except socket.timeout:
            logger.debug(f"Timeout connecting to MikroTik API at {vpn_ip}:{api_port}")
            return False
        except socket.gaierror:
            logger.debug(f"Invalid IP address: {vpn_ip}")
            return False
        except Exception as e:
            logger.error(f"Error testing MikroTik API connection: {str(e)}")
            return False

    @staticmethod
    def connect(
        host: str,
        username: str,
        password: str,
        port: int = 8728,
        timeout: int = 10
    ):
        """
        Connect to MikroTik router via API.

        Args:
            host: Router IP address (VPN IP)
            username: API username
            password: API password
            port: API port (default 8728)
            timeout: Connection timeout in seconds

        Returns:
            RouterOS API connection object

        Raises:
            HTTPException: If connection fails
        """
        try:
            logger.info(f"Connecting to MikroTik API at {host}:{port} with user {username}")
            # routeros_api.api.connect signature: (host, username, password, port=8728, timeout=10, use_ssl=False)
            connection = connect(host, username, password, port=port, timeout=timeout)
            logger.info(f"Successfully connected to MikroTik API at {host}:{port}")
            return connection
        except Exception as e:
            logger.error(f"Failed to connect to MikroTik API at {host}:{port}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to connect to MikroTik router: {str(e)}"
            )

    @staticmethod
    def check_profile_exists(
        connection,
        profile_name: str,
        package_type: str
    ) -> bool:
        """
        Check if a profile exists on MikroTik router.

        Args:
            connection: RouterOsApi connection object
            profile_name: Profile name to check
            package_type: Package type (pppoe, hotspot, static)

        Returns:
            True if profile exists, False otherwise
        """
        try:
            if package_type == "pppoe":
                resource = connection.get_resource("/ppp/profile")
            elif package_type == "hotspot":
                resource = connection.get_resource("/ip/hotspot/user/profile")
            elif package_type == "static":
                resource = connection.get_resource("/queue/simple")
            else:
                logger.error(f"Unknown package type: {package_type}")
                return False

            profiles = resource.get(name=profile_name)
            exists = len(profiles) > 0
            logger.info(f"Profile '{profile_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking profile existence: {str(e)}")
            return False

    @staticmethod
    def create_pppoe_profile(
        connection,
        profile_name: str,
        download_speed: int,
        upload_speed: int,
        session_timeout: str
    ) -> None:
        """
        Create PPPoE profile on MikroTik router.

        Args:
            connection: RouterOsApi connection object
            profile_name: Profile name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps
            session_timeout: Session timeout (e.g., "30d", "12h", "90m")

        Raises:
            HTTPException: If profile creation fails
        """
        try:
            logger.info(f"Creating PPPoE profile '{profile_name}' with rate-limit {download_speed}M/{upload_speed}M, session-timeout {session_timeout}")
            resource = connection.get_resource("/ppp/profile")
            resource.add(
                name=profile_name,
                rate_limit=f"{download_speed}M/{upload_speed}M",
                session_timeout=session_timeout
            )
            logger.info(f"Successfully created PPPoE profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to create PPPoE profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create PPPoE profile: {str(e)}"
            )

    @staticmethod
    def create_hotspot_profile(
        connection,
        profile_name: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Create Hotspot user profile on MikroTik router.

        Args:
            connection: RouterOsApi connection object
            profile_name: Profile name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If profile creation fails
        """
        try:
            logger.info(f"Creating Hotspot profile '{profile_name}' with rate-limit {download_speed}M/{upload_speed}M")
            resource = connection.get_resource("/ip/hotspot/user/profile")
            resource.add(
                name=profile_name,
                rate_limit=f"{download_speed}M/{upload_speed}M",
                shared_users=1
            )
            logger.info(f"Successfully created Hotspot profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to create Hotspot profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create Hotspot profile: {str(e)}"
            )

    @staticmethod
    def create_static_queue(
        connection,
        queue_name: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Create simple queue on MikroTik router for static IP packages.

        Args:
            connection: RouterOsApi connection object
            queue_name: Queue name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If queue creation fails
        """
        try:
            logger.info(f"Creating static queue '{queue_name}' with max-limit {download_speed}M/{upload_speed}M")
            resource = connection.get_resource("/queue/simple")
            resource.add(
                name=queue_name,
                max_limit=f"{download_speed}M/{upload_speed}M"
            )
            logger.info(f"Successfully created static queue '{queue_name}'")
        except Exception as e:
            logger.error(f"Failed to create static queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create static queue: {str(e)}"
            )


# Global instance
mikrotik_service = MikroTikService()

