"""VPN user management service for OpenVPN.

This service executes OpenVPN user management commands on the host machine
via SSH, not inside the Docker container.
"""

import logging
import subprocess
from typing import Optional

from fastapi import HTTPException, status

from app.config import get_settings

logger = logging.getLogger(__name__)

settings = get_settings()
OVPN_USER_SCRIPT = "/usr/local/bin/ovpn-user.sh"


class VPNService:
    """Service for managing OpenVPN users."""

    @staticmethod
    def _build_ssh_command(remote_command: str) -> list:
        """
        Build SSH command to execute on host machine.

        Args:
            remote_command: Command to execute on remote host

        Returns:
            List of command arguments for subprocess
        """
        # Ensure SSH options have valid values
        strict_host_check = settings.SSH_STRICT_HOST_KEY_CHECKING or "no"
        
        ssh_opts = [
            "-o", f"StrictHostKeyChecking={strict_host_check}",
            "-o", "UserKnownHostsFile=/dev/null",
            "-o", "LogLevel=ERROR",
            "-i", settings.SSH_KEY_PATH,
            "-p", str(settings.SSH_PORT)
        ]

        ssh_target = f"{settings.SSH_USER}@{settings.SSH_HOST}"
        return ["ssh"] + ssh_opts + [ssh_target, remote_command]

    @staticmethod
    def add_vpn_user(username: str, password: str) -> bool:
        """
        Add a VPN user to OpenVPN by executing ovpn-user.sh script on host via SSH.

        Args:
            username: VPN username
            password: VPN password

        Returns:
            True if user added successfully

        Raises:
            HTTPException: If user creation fails
        """
        try:
            # Escape password for shell command (handle special characters)
            import shlex
            escaped_password = shlex.quote(password)
            
            # Build remote command to execute on host
            remote_command = f"{OVPN_USER_SCRIPT} add {shlex.quote(username)} {escaped_password}"
            
            # Build SSH command
            ssh_cmd = VPNService._build_ssh_command(remote_command)
            
            logger.info(f"Executing via SSH: {' '.join(ssh_cmd[:3])}... {ssh_cmd[-2]} '{remote_command}'")

            # Execute SSH command
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=True  # Raise exception on non-zero return code
            )

            # Log output
            logger.info(f"SSH command executed successfully")
            if result.stdout:
                logger.info(f"SSH stdout: {result.stdout.strip()}")
            if result.stderr:
                logger.debug(f"SSH stderr: {result.stderr.strip()}")

            logger.info(f"VPN user {username} added successfully on host via SSH")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while adding VPN user {username} via SSH")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Timeout while creating VPN user: SSH command timed out"
            )
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.strip() if e.stderr else e.stdout.strip() if e.stdout else "Unknown SSH error"
            logger.error(
                f"Failed to add VPN user {username} via SSH. "
                f"Return code: {e.returncode}, Error: {error_msg}"
            )
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create VPN user on host: {error_msg}"
            )
        except FileNotFoundError:
            logger.error(f"SSH command not found. Is OpenSSH client installed?")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SSH client not available. Cannot execute VPN user management on host."
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
        Delete a VPN user from OpenVPN by executing ovpn-user.sh script on host via SSH.

        Args:
            username: VPN username

        Returns:
            True if user deleted successfully

        Raises:
            HTTPException: If user deletion fails
        """
        try:
            # Build remote command to execute on host
            import shlex
            remote_command = f"{OVPN_USER_SCRIPT} del {shlex.quote(username)}"
            
            # Build SSH command
            ssh_cmd = VPNService._build_ssh_command(remote_command)
            
            logger.info(f"Executing via SSH: {' '.join(ssh_cmd[:3])}... {ssh_cmd[-2]} '{remote_command}'")

            # Execute SSH command
            result = subprocess.run(
                ssh_cmd,
                capture_output=True,
                text=True,
                timeout=30,
                check=False  # Don't raise on error, check return code manually
            )

            if result.returncode != 0:
                error_msg = result.stderr.strip() if result.stderr else result.stdout.strip() if result.stdout else "Unknown error"
                logger.warning(f"SSH command returned non-zero code: {result.returncode}, Error: {error_msg}")
                
                # Don't raise exception if user doesn't exist
                if "not found" in error_msg.lower() or "does not exist" in error_msg.lower():
                    logger.info(f"VPN user {username} does not exist on host, skipping deletion")
                    return True
                    
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail=f"Failed to delete VPN user on host: {error_msg}"
                )

            logger.info(f"VPN user {username} deleted successfully on host via SSH")
            if result.stdout:
                logger.info(f"SSH stdout: {result.stdout.strip()}")
            return True

        except subprocess.TimeoutExpired:
            logger.error(f"Timeout while deleting VPN user {username} via SSH")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Timeout while deleting VPN user: SSH command timed out"
            )
        except FileNotFoundError:
            logger.error(f"SSH command not found. Is OpenSSH client installed?")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="SSH client not available. Cannot execute VPN user management on host."
            )
        except HTTPException:
            # Re-raise HTTP exceptions
            raise
        except Exception as e:
            logger.error(f"Unexpected error deleting VPN user {username}: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to delete VPN user: {str(e)}"
            )


# Global instance
vpn_service = VPNService()

