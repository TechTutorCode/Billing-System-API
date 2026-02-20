"""MikroTik API service for testing router connectivity and executing commands."""

import logging
import socket
from typing import Dict, List, Optional, Any

from fastapi import HTTPException, status
import routeros_api

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
            # TODO: remove password from logs before production
            logger.info(
                "Connecting to MikroTik API at %s:%s username=%s password=%s",
                host, port, username, password,
            )
            # Try encrypted login first (older RouterOS); fall back to plaintext (6.43+)
            for plaintext in (False, True):
                try:
                    connection_pool = routeros_api.RouterOsApiPool(
                        host=host,
                        username=username,
                        password=password,
                        port=port,
                        plaintext_login=plaintext,
                    )
                    api = connection_pool.get_api()
                    logger.info(
                        "Successfully connected to MikroTik API at %s:%s (plaintext_login=%s)",
                        host, port, plaintext,
                    )
                    return {"pool": connection_pool, "api": api}
                except Exception as conn_err:
                    if getattr(conn_err, "__module__", "").startswith("routeros_api"):
                        logger.warning(
                            "MikroTik API connect with plaintext_login=%s failed: %s; %s",
                            plaintext, type(conn_err).__name__, conn_err,
                        )
                        if plaintext is False:
                            continue
                    raise
        except Exception as e:
            error_msg = str(e)
            exc_name = type(e).__name__
            logger.error(f"Failed to connect to MikroTik API at {host}:{port}: {error_msg}")

            # Connection closed during login = router rejected us (wrong credentials or no API access)
            if exc_name == "RouterOsApiConnectionClosedError":
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail=(
                        "MikroTik closed the connection during login. "
                        "Check: (1) Username and password for this router are correct in the app. "
                        "(2) On the router, the API user exists and has a group with API (or full) access. "
                        "(3) IP → Services: API is enabled."
                    ),
                )
            if "invalid user name or password" in error_msg.lower() or "password" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_401_UNAUTHORIZED,
                    detail="MikroTik API authentication failed. Please verify the username and password are correct, and that the API user has API access enabled on the router."
                )
            if "connection" in error_msg.lower() or "refused" in error_msg.lower() or "timeout" in error_msg.lower():
                raise HTTPException(
                    status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                    detail=f"Cannot connect to MikroTik router at {host}:{port}. Please verify the router is online and the API port is accessible."
                )
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Failed to connect to MikroTik router: {error_msg}"
            )

    @staticmethod
    def check_profile_exists(
        connection_dict,
        profile_name: str,
        package_type: str
    ) -> bool:
        """
        Check if a profile exists on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name to check
            package_type: Package type (pppoe, hotspot, static)

        Returns:
            True if profile exists, False otherwise
        """
        try:
            api = connection_dict["api"]
            if package_type == "pppoe":
                resource = api.get_resource("/ppp/profile")
            elif package_type == "hotspot":
                resource = api.get_resource("/ip/hotspot/user/profile")
            elif package_type == "static":
                resource = api.get_resource("/queue/simple")
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
        connection_dict,
        profile_name: str,
        download_speed: int,
        upload_speed: int,
        session_timeout: str
    ) -> None:
        """
        Create PPPoE profile on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps
            session_timeout: Session timeout (e.g., "30d", "12h", "90m")

        Raises:
            HTTPException: If profile creation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Creating PPPoE profile '{profile_name}' with rate-limit {download_speed}M/{upload_speed}M, session-timeout {session_timeout}")
            resource = api.get_resource("/ppp/profile")
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
        connection_dict,
        profile_name: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Create Hotspot user profile on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If profile creation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Creating Hotspot profile '{profile_name}' with rate-limit {download_speed}M/{upload_speed}M")
            resource = api.get_resource("/ip/hotspot/user/profile")
            resource.add(
                name=profile_name,
                rate_limit=f"{download_speed}M/{upload_speed}M",
                shared_users="1"
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
        connection_dict,
        queue_name: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Create simple queue on MikroTik router for static IP packages.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If queue creation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Creating static queue '{queue_name}' with max-limit {download_speed}M/{upload_speed}M")
            resource = api.get_resource("/queue/simple")
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

    @staticmethod
    def remove_profile(
        connection_dict,
        profile_name: str,
        package_type: str
    ) -> None:
        """
        Remove profile from MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name to remove
            package_type: Package type (pppoe, hotspot, static)

        Raises:
            HTTPException: If profile removal fails
        """
        try:
            api = connection_dict["api"]
            
            if package_type == "pppoe":
                resource = api.get_resource("/ppp/profile")
            elif package_type == "hotspot":
                resource = api.get_resource("/ip/hotspot/user/profile")
            elif package_type == "static":
                resource = api.get_resource("/queue/simple")
            else:
                logger.error(f"Unknown package type: {package_type}")
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Unknown package type: {package_type}"
                )

            # Check if profile exists
            profiles = resource.get(name=profile_name)
            if not profiles:
                logger.warning(f"Profile '{profile_name}' not found on router, skipping removal")
                return

            # Remove profile
            resource.remove(id=profiles[0]["id"])
            logger.info(f"Successfully removed {package_type} profile '{profile_name}' from router")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to remove {package_type} profile '{profile_name}': {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove {package_type} profile: {str(e)}"
            )

    @staticmethod
    def update_pppoe_profile(
        connection_dict,
        profile_name: str,
        download_speed: int,
        upload_speed: int,
        session_timeout: str
    ) -> None:
        """
        Update PPPoE profile on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps
            session_timeout: Session timeout (e.g., "30d", "12h", "90m")

        Raises:
            HTTPException: If profile update fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Updating PPPoE profile '{profile_name}' with rate-limit {download_speed}M/{upload_speed}M, session-timeout {session_timeout}")
            resource = api.get_resource("/ppp/profile")
            
            # Get existing profile
            profiles = resource.get(name=profile_name)
            if not profiles:
                logger.warning(f"PPPoE profile '{profile_name}' not found, creating new one")
                resource.add(
                    name=profile_name,
                    rate_limit=f"{download_speed}M/{upload_speed}M",
                    session_timeout=session_timeout
                )
            else:
                # Update existing profile
                resource.set(
                    id=profiles[0]["id"],
                    rate_limit=f"{download_speed}M/{upload_speed}M",
                    session_timeout=session_timeout
                )
            logger.info(f"Successfully updated PPPoE profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to update PPPoE profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update PPPoE profile: {str(e)}"
            )

    @staticmethod
    def update_hotspot_profile(
        connection_dict,
        profile_name: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Update Hotspot user profile on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            profile_name: Profile name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If profile update fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Updating Hotspot profile '{profile_name}' with rate-limit {download_speed}M/{upload_speed}M")
            resource = api.get_resource("/ip/hotspot/user/profile")
            
            # Get existing profile
            profiles = resource.get(name=profile_name)
            if not profiles:
                logger.warning(f"Hotspot profile '{profile_name}' not found, creating new one")
                resource.add(
                    name=profile_name,
                    rate_limit=f"{download_speed}M/{upload_speed}M",
                    shared_users="1"
                )
            else:
                # Update existing profile
                resource.set(
                    id=profiles[0]["id"],
                    rate_limit=f"{download_speed}M/{upload_speed}M"
                )
            logger.info(f"Successfully updated Hotspot profile '{profile_name}'")
        except Exception as e:
            logger.error(f"Failed to update Hotspot profile: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update Hotspot profile: {str(e)}"
            )

    @staticmethod
    def update_static_queue(
        connection_dict,
        queue_name: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Update simple queue on MikroTik router for static IP packages.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If queue update fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Updating static queue '{queue_name}' with max-limit {download_speed}M/{upload_speed}M")
            resource = api.get_resource("/queue/simple")
            
            # Get existing queue
            queues = resource.get(name=queue_name)
            if not queues:
                logger.warning(f"Static queue '{queue_name}' not found, creating new one")
                resource.add(
                    name=queue_name,
                    max_limit=f"{download_speed}M/{upload_speed}M"
                )
            else:
                # Update existing queue
                resource.set(
                    id=queues[0]["id"],
                    max_limit=f"{download_speed}M/{upload_speed}M"
                )
            logger.info(f"Successfully updated static queue '{queue_name}'")
        except Exception as e:
            logger.error(f"Failed to update static queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to update static queue: {str(e)}"
            )


    @staticmethod
    def configure_radius_for_ppp(
        connection_dict,
        radius_server_ip: str,
        radius_secret: str,
        auth_port: int = 1812,
        acct_port: int = 1813,
    ) -> None:
        """
        Add RADIUS clients for PPP and Hotspot and enable PPP AAA use-radius.
        - Adds /radius client with service=ppp (and service=hotspot if missing).
        - Sets /ppp/aaa use-radius=yes, accounting=yes.
        Idempotent: skips add if a client for this server+service already exists.

        Args:
            connection_dict: From connect() with 'pool' and 'api' keys.
            radius_server_ip: FreeRADIUS server IP.
            radius_secret: Shared secret (never logged).
            auth_port: RADIUS auth port (default 1812).
            acct_port: RADIUS accounting port (default 1813).

        Raises:
            HTTPException: If API calls fail.
        """
        try:
            api = connection_dict["api"]
            resource = api.get_resource("/radius")
            server_ip_str = str(radius_server_ip).strip()
            radius_list = resource.get() or []
            def has_client(service: str) -> bool:
                for item in radius_list:
                    if not isinstance(item, dict):
                        continue
                    addr = item.get("address")
                    svc = item.get("service")
                    if addr and str(addr).strip() == server_ip_str and svc and service.lower() in str(svc).lower():
                        return True
                return False
            base_attrs = {
                "address": radius_server_ip,
                "secret": radius_secret,
                "authentication-port": str(auth_port),
                "accounting-port": str(acct_port),
                "disabled": "false",
            }
            if not has_client("ppp"):
                resource.add(**{**base_attrs, "service": "ppp"})
                logger.info("RADIUS client added for PPP", extra={"address": radius_server_ip})
            else:
                logger.info("RADIUS client for PPP already present", extra={"address": radius_server_ip})
            if not has_client("hotspot"):
                resource.add(**{**base_attrs, "service": "hotspot"})
                logger.info("RADIUS client added for Hotspot", extra={"address": radius_server_ip})
            else:
                logger.info("RADIUS client for Hotspot already present", extra={"address": radius_server_ip})
            # RouterOS v7: /ppp/aaa is singleton — set use-radius and accounting for PPP
            aaa = api.get_resource("/ppp/aaa")
            aaa.set(**{"use-radius": "yes", "accounting": "yes"})
            logger.info("PPP AAA set use-radius=yes accounting=yes")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to configure RADIUS on MikroTik: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to configure RADIUS on MikroTik: {str(e)}"
            )

    @staticmethod
    def verify_radius_for_ppp(
        connection_dict,
        radius_server_ip: str,
    ) -> bool:
        """
        Check if RADIUS for PPP and Hotspot is still configured on the router.
        Returns True only if:
        - /radius has an entry for this server with service=ppp
        - /radius has an entry for this server with service=hotspot
        - /ppp/aaa has use-radius=yes
        Returns False if any is missing or API fails. Used to set radius_configured=False when removed.
        """
        try:
            api = connection_dict["api"]
            radius_resource = api.get_resource("/radius")
            radius_list = radius_resource.get() or []
            server_ip_str = str(radius_server_ip).strip()
            has_ppp = False
            has_hotspot = False
            for item in radius_list:
                if not isinstance(item, dict):
                    continue
                addr = item.get("address")
                svc = item.get("service")
                if not addr or str(addr).strip() != server_ip_str or not svc:
                    continue
                svc_lower = str(svc).lower()
                if "ppp" in svc_lower:
                    has_ppp = True
                if "hotspot" in svc_lower:
                    has_hotspot = True
            if not has_ppp:
                logger.info("RADIUS verify: no PPP RADIUS client for %s on router", server_ip_str)
                return False
            if not has_hotspot:
                logger.info("RADIUS verify: no Hotspot RADIUS client for %s on router", server_ip_str)
                return False
            aaa_resource = api.get_resource("/ppp/aaa")
            aaa_list = aaa_resource.get()
            if not aaa_list or len(aaa_list) == 0:
                logger.info("RADIUS verify: PPP AAA empty or missing on router")
                return False
            use_radius_yes = False
            for item in aaa_list:
                if not isinstance(item, dict):
                    continue
                use_radius = item.get("use-radius")
                if use_radius and str(use_radius).lower() in ("yes", "true", "1"):
                    use_radius_yes = True
                    break
            if not use_radius_yes:
                logger.info("RADIUS verify: PPP AAA use-radius is not yes on router")
                return False
            logger.debug("RADIUS verify: PPP and Hotspot RADIUS config present, PPP AAA use-radius=yes")
            return True
        except Exception as e:
            logger.warning("RADIUS verify failed: %s", e)
            return False


# Global instance
mikrotik_service = MikroTikService()

