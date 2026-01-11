"""MikroTik API service for testing router connectivity."""

import logging
import socket
from typing import Optional

from fastapi import HTTPException, status

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


# Global instance
mikrotik_service = MikroTikService()

