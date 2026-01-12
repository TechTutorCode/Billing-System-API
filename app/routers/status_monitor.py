"""Background task for monitoring router status from OpenVPN logs."""

import logging
import re
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional

from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.routers.models import Router, RouterStatus
from app.routers.services import router_service
from app.routers.mikrotik_service import mikrotik_service

logger = logging.getLogger(__name__)

settings = get_settings()
OPENVPN_STATUS_LOG = settings.OPENVPN_STATUS_LOG


def _build_ssh_command(remote_command: str) -> list:
    """
    Build SSH command to execute on host machine (same as VPN service).

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
        "-p", str(settings.SSH_PORT)
    ]
    
    # Use password authentication if password is provided
    if settings.SSH_PASSWORD:
        # Use sshpass for password-based authentication
        ssh_cmd = ["sshpass", "-p", settings.SSH_PASSWORD, "ssh"] + ssh_opts
    elif settings.SSH_KEY_PATH:
        # Use SSH key authentication
        import os
        if os.path.exists(settings.SSH_KEY_PATH):
            ssh_opts.extend(["-i", settings.SSH_KEY_PATH])
        ssh_cmd = ["ssh"] + ssh_opts
    else:
        raise ValueError("SSH authentication not configured. Please set either SSH_PASSWORD or SSH_KEY_PATH")

    ssh_target = f"{settings.SSH_USER}@{settings.SSH_HOST}"
    return ssh_cmd + [ssh_target, remote_command]


def parse_openvpn_status_log() -> Dict[str, str]:
    """
    Parse OpenVPN status log to extract VPN IPs mapped to usernames.
    Reads the log file from the host machine via SSH.

    OpenVPN status log format:
    CLIENT_LIST: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
    ROUTING_TABLE: Virtual Address,Common Name,Real Address,Last Ref

    Returns:
        Dictionary mapping vpn_username to vpn_ip
    """
    username_to_ip: Dict[str, str] = {}

    try:
        # Read OpenVPN status log from host machine via SSH
        remote_command = f"cat {OPENVPN_STATUS_LOG}"
        ssh_cmd = _build_ssh_command(remote_command)
        
        logger.debug(f"Reading OpenVPN status log from host via SSH: {OPENVPN_STATUS_LOG}")
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip() or "Unknown error"
            logger.warning(f"Failed to read OpenVPN status log via SSH: {error_msg}")
            return username_to_ip
        
        content = result.stdout

        # Parse ROUTING_TABLE section to get Virtual Address mapped to Common Name
        # Format: Virtual Address,Common Name,Real Address,Last Ref
        routing_section_match = re.search(
            r"ROUTING_TABLE\s+(.*?)(?=GLOBAL STATS|END|$)",
            content,
            re.DOTALL
        )

        if routing_section_match:
            routing_lines = routing_section_match.group(1).strip().split("\n")
            for line in routing_lines:
                if not line.strip() or line.startswith("Virtual"):
                    continue

                # Parse line: Virtual Address,Common Name,Real Address,Last Ref
                parts = line.split(",")
                if len(parts) >= 2:
                    virtual_ip = parts[0].strip()
                    username = parts[1].strip()
                    if username and virtual_ip:
                        username_to_ip[username] = virtual_ip
                        logger.debug(f"Found router {username} with VPN IP {virtual_ip}")

        # Also verify in CLIENT_LIST that the router is actually connected
        client_section_match = re.search(
            r"CLIENT_LIST\s+(.*?)(?=ROUTING_TABLE|$)",
            content,
            re.DOTALL
        )

        if client_section_match:
            connected_usernames = set()
            client_lines = client_section_match.group(1).strip().split("\n")
            for line in client_lines:
                if not line.strip() or line.startswith("Common"):
                    continue

                # Parse line: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
                parts = line.split(",")
                if len(parts) >= 1:
                    username = parts[0].strip()
                    if username:
                        connected_usernames.add(username)

            # Only keep routers that are in both CLIENT_LIST and ROUTING_TABLE
            username_to_ip = {
                username: ip 
                for username, ip in username_to_ip.items() 
                if username in connected_usernames
            }

    except subprocess.TimeoutExpired:
        logger.error(f"Timeout reading OpenVPN status log via SSH")
    except subprocess.CalledProcessError as e:
        error_msg = e.stderr.strip() if e.stderr else e.stdout.strip() or "Unknown error"
        logger.warning(f"Failed to read OpenVPN status log via SSH: {error_msg}")
    except FileNotFoundError:
        logger.warning(f"SSH command not found. Is OpenSSH client installed?")
    except Exception as e:
        logger.error(f"Error parsing OpenVPN status log: {str(e)}")

    return username_to_ip


def update_router_statuses():
    """
    Background task to update router statuses based on OpenVPN log and API tests.
    """
    db: Session = SessionLocal()
    try:
        # Get all active routers
        routers = db.query(Router).filter(Router.is_active == True).all()

        if not routers:
            return

        # Parse OpenVPN status log
        username_to_ip = parse_openvpn_status_log()
        
        logger.info(f"Parsed {len(username_to_ip)} routers from OpenVPN status log: {username_to_ip}")

        for router in routers:
            try:
                vpn_ip = username_to_ip.get(router.vpn_username)
                logger.debug(f"Checking router {router.vpn_username} (current status: {router.status}, current VPN IP: {router.vpn_ip})")

                if vpn_ip:
                    # Router is connected to VPN
                    if router.vpn_ip != vpn_ip:
                        # Update VPN IP
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            vpn_ip=vpn_ip,
                            status=RouterStatus.VPN_CONNECTED
                        )

                    # Test MikroTik API connection (use the newly parsed vpn_ip)
                    if mikrotik_service.test_api_connection(vpn_ip, router.api_port):
                        # API is accessible, router is online
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            status=RouterStatus.ONLINE
                        )
                    else:
                        # VPN connected but API not accessible
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            status=RouterStatus.VPN_CONNECTED
                        )
                else:
                    # Router not in VPN log, mark as offline
                    if router.status != RouterStatus.PENDING.value:
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            status=RouterStatus.OFFLINE
                        )

            except Exception as e:
                logger.error(f"Error updating status for router {router.id}: {str(e)}")
                continue

    except Exception as e:
        logger.error(f"Error in router status monitor: {str(e)}")
    finally:
        db.close()


def start_status_monitor():
    """
    Start background task for router status monitoring.
    This should be called from a background task scheduler (e.g., APScheduler, Celery, or asyncio).
    """
    import asyncio
    import time

    async def monitor_loop():
        while True:
            try:
                update_router_statuses()
                # Run every 60 seconds
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in status monitor loop: {str(e)}")
                await asyncio.sleep(60)

    # Run in background
    asyncio.create_task(monitor_loop())

