"""VPN user management service for OpenVPN."""

import logging
import subprocess
from typing import Optional

from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

OVPN_USER_SCRIPT = "/usr/local/bin/ovpn-user.sh"


class VPNService:
    """Service for managing OpenVPN users."""

    @staticmethod
    def add_vpn_user(username: str, password: str) -> bool:
        """
        Add a VPN user to OpenVPN using ovpn-user.sh script.

        Args:
            username: VPN username
            password: VPN password

        Returns:
            True if user added successfully

        Raises:
            HTTPException: If user creation fails
        """
        try:
            # Check if script exists
            import os
            if not os.path.exists(OVPN_USER_SCRIPT):
                logger.error(f"VPN script not found at {OVPN_USER_SCRIPT}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"VPN user management script not found at {OVPN_USER_SCRIPT}"
                )

            # Check if script is executable
            if not os.access(OVPN_USER_SCRIPT, os.X_OK):
                logger.error(f"VPN script is not executable: {OVPN_USER_SCRIPT}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"VPN user management script is not executable"
                )

            logger.info(f"Calling VPN script: {OVPN_USER_SCRIPT} add {username}")
            
            # Call ovpn-user.sh add command with sudo (required to write to /etc/openvpn/psw-file)
            result = subprocess.run(
                [ OVPN_USER_SCRIPT, "add", username, password],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )

            # Log full output for debugging
            logger.info(f"Script return code: {result.returncode}")
            logger.info(f"Script stdout: {result.stdout}")
            logger.info(f"Script stderr: {result.stderr}")

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip() or "Unknown error"
                logger.error(f"Failed to add VPN user {username}. Return code: {result.returncode}, Error: {error_msg}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to create VPN user: {error_msg}"
                )

            # Verify user was actually added to psw-file
            import os
            psw_file = "/etc/openvpn/psw-file"
            if os.path.exists(psw_file):
                try:
                    with open(psw_file, 'r') as f:
                        content = f.read()
                        if f"{username}:" in content:
                            logger.info(f"Verified: VPN user {username} exists in {psw_file}")
                        else:
                            logger.warning(f"Warning: VPN user {username} not found in {psw_file} after creation")
                except PermissionError:
                    logger.warning(f"Cannot verify {psw_file} - permission denied (this is expected if not running as root)")
                except Exception as e:
                    logger.warning(f"Could not verify {psw_file}: {str(e)}")

            logger.info(f"VPN user {username} added successfully. Output: {result.stdout.strip()}")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while adding VPN user {username}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Timeout while creating VPN user"
            )
        except FileNotFoundError:
            logger.error(f"ovpn-user.sh script not found at {OVPN_USER_SCRIPT}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN user management script not found"
            )
        except Exception as e:
            logger.error(f"Unexpected error adding VPN user {username}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create VPN user: {str(e)}"
            )

    @staticmethod
    def delete_vpn_user(username: str) -> bool:
        """
        Delete a VPN user from OpenVPN using ovpn-user.sh script.

        Args:
            username: VPN username

        Returns:
            True if user deleted successfully

        Raises:
            HTTPException: If user deletion fails
        """
        try:
            # Call ovpn-user.sh del command with sudo
            result = subprocess.run(
                ["sudo", OVPN_USER_SCRIPT, "del", username],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )

            if result.returncode != 0:
                error_msg = result.stderr or result.stdout or "Unknown error"
                logger.warning(f"Failed to delete VPN user {username}: {error_msg}")
                # Don't raise exception if user doesn't exist
                if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                    logger.info(f"VPN user {username} does not exist, skipping deletion")
                    return True
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete VPN user: {error_msg}"
                )

            logger.info(f"VPN user {username} deleted successfully")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while deleting VPN user {username}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Timeout while deleting VPN user"
            )
        except FileNotFoundError:
            logger.error(f"ovpn-user.sh script not found at {OVPN_USER_SCRIPT}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="VPN user management script not found"
            )
        except Exception as e:
            logger.error(f"Unexpected error deleting VPN user {username}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete VPN user: {str(e)}"
            )


# Global instance
vpn_service = VPNService()

