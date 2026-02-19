"""Background task for monitoring router status from OpenVPN logs."""

import re
import subprocess
from datetime import datetime, timezone
from typing import Dict, Optional, Tuple

from dateutil import parser as date_parser
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import SessionLocal
from app.radius.service import radius_service
from app.routers.models import Router, RouterStatus
from app.routers.services import router_service
from app.routers.mikrotik_service import mikrotik_service
from app.routers.status_history_models import RouterStatusHistory

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


def parse_openvpn_status_log() -> Dict[str, Tuple[str, Optional[str]]]:
    """
    Parse OpenVPN status log to extract VPN IPs mapped to usernames.
    Reads the log file from the host machine via SSH.

    OpenVPN status log format:
    CLIENT_LIST: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
    ROUTING_TABLE: Virtual Address,Common Name,Real Address,Last Ref

    Returns:
        Dictionary mapping vpn_username to (vpn_ip, connected_since)
        connected_since is a string timestamp or None
    """
    
    username_to_ip: Dict[str, str] = {}
    username_to_connected_since: Dict[str, str] = {}

    try:
        # Read OpenVPN status log from host machine via SSH
        # Test SSH connection first
        test_cmd = _build_ssh_command("echo 'SSH_TEST_SUCCESS'")
        test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10, check=False)
        
        if test_result.returncode != 0:
            return username_to_ip
        
        # Use sudo to read the file (it's in /var/log/ which may require root)
        remote_command = f"sudo cat {OPENVPN_STATUS_LOG} 2>&1"
        ssh_cmd = _build_ssh_command(remote_command)
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        if result.returncode != 0:
            return username_to_ip
        
        content = result.stdout
        
        # Check if content is empty or contains error
        if not content or len(content.strip()) == 0:
            # Try to check if file exists with proper path
            check_cmd = _build_ssh_command(f"test -f {OPENVPN_STATUS_LOG} && echo 'FILE_EXISTS' || (echo 'FILE_NOT_FOUND' && ls -la /var/log/ | grep -i openvpn)")
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10, check=False)
            
            # Also try to see what's in /var/log/ and check the actual file
            list_cmd = _build_ssh_command(f"ls -la /var/log/ | grep -i openvpn")
            list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10, check=False)
            
            # Try reading with sudo in case of permissions
            sudo_cmd = _build_ssh_command(f"sudo cat {OPENVPN_STATUS_LOG} 2>&1")
            sudo_result = subprocess.run(sudo_cmd, capture_output=True, text=True, timeout=10, check=False)
            if sudo_result.stdout and len(sudo_result.stdout.strip()) > 0:
                content = sudo_result.stdout
                # Continue with parsing instead of returning
            else:
                return username_to_ip
        
        # Check if file was not found (error message in content)
        if "No such file" in content or "cannot access" in content.lower() or "Permission denied" in content:
            return username_to_ip
        
        # Check if file was not found
        if "FILE_NOT_FOUND" in content:
            return username_to_ip

        # Parse ROUTING TABLE section to get Virtual Address mapped to Common Name
        # Format: Virtual Address,Common Name,Real Address,Last Ref
        # Note: The header is "ROUTING TABLE" (with space, not underscore)
        routing_section_match = re.search(
            r"ROUTING TABLE\s+(.*?)(?=GLOBAL STATS|END|$)",
            content,
            re.DOTALL
        )

        if routing_section_match:
            routing_content = routing_section_match.group(1).strip()
            
            routing_lines = routing_content.split("\n")
            
            for i, line in enumerate(routing_lines):
                if not line.strip() or line.startswith("Virtual"):
                    continue

                # Parse line: Virtual Address,Common Name,Real Address,Last Ref
                parts = line.split(",")
                if len(parts) >= 2:
                    virtual_ip = parts[0].strip()
                    username = parts[1].strip()
                    if username and virtual_ip:
                        username_to_ip[username] = virtual_ip

        # Also verify in CLIENT LIST that the router is actually connected
        # Note: The header is "OpenVPN CLIENT LIST" (with "OpenVPN" prefix)
        client_section_match = re.search(
            r"OpenVPN CLIENT LIST\s+(.*?)(?=ROUTING TABLE|$)",
            content,
            re.DOTALL
        )

        if client_section_match:
            client_content = client_section_match.group(1).strip()
            
            connected_usernames = set()
            client_lines = client_content.split("\n")
            
            for i, line in enumerate(client_lines):
                # Skip header lines: "Updated,..." and "Common Name,..."
                if not line.strip() or line.startswith("Common") or line.startswith("Updated"):
                    continue

                # Parse line: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
                parts = line.split(",")
                if len(parts) >= 1:
                    username = parts[0].strip()
                    if username:
                        connected_usernames.add(username)
                        # Extract Connected Since (5th column, index 4)
                        if len(parts) >= 5:
                            connected_since = parts[4].strip()
                            username_to_connected_since[username] = connected_since

            # Only keep routers that are in both CLIENT LIST and ROUTING TABLE
            # Build result dict with tuples (vpn_ip, connected_since)
            username_to_ip = {
                username: (ip, username_to_connected_since.get(username))
                for username, ip in username_to_ip.items() 
                if username in connected_usernames
            }

    except subprocess.TimeoutExpired:
        pass
    except subprocess.CalledProcessError as e:
        pass
    except FileNotFoundError:
        pass
    except Exception as e:
        pass

    # Convert username_to_ip from Dict[str, str] to Dict[str, Tuple[str, Optional[str]]]
    # This handles the case where CLIENT LIST was not found but ROUTING TABLE had entries
    if username_to_ip:
        # Check if values are strings (need conversion) or tuples (already converted)
        first_value = next(iter(username_to_ip.values()))
        if isinstance(first_value, str):
            # Need to convert to tuple format
            result: Dict[str, Tuple[str, Optional[str]]] = {
                username: (ip, username_to_connected_since.get(username))
                for username, ip in username_to_ip.items()
            }
            return result
    
    # If already in tuple format or empty, return as is
    return username_to_ip if username_to_ip else {}


def _ensure_router_radius_setup(db: Session, router: Router, vpn_ip: str) -> None:
    """
    When router has vpn_ip and API is reachable: insert NAS in RADIUS DB and
    auto-configure MikroTik RADIUS client + PPP AAA. Then mark router.radius_configured.
    vpn_ip is passed explicitly (from OpenVPN log) to avoid relying on router.vpn_ip sync.
    """
    import logging
    import traceback
    logger = logging.getLogger(__name__)
    # Treat None radius_configured as False (e.g. column added later without default)
    already_done = bool(router.radius_configured)
    if not vpn_ip or not router.radius_secret or already_done:
        return
    connection = None
    try:
        radius_service.add_nas(vpn_ip, router.name, router.radius_secret)
        api_user = router.mikrotik_api_username or "admin"
        api_pass = router.mikrotik_api_password
        if not api_pass:
            logger.warning(
                "Router %s (%s): no MikroTik API password, skipping RADIUS config",
                router.id, router.name,
            )
            return
        connection = mikrotik_service.connect(
            host=vpn_ip,
            username=api_user,
            password=api_pass,
            port=router.api_port,
        )
        mikrotik_service.configure_radius_for_ppp(
            connection,
            radius_server_ip=settings.RADIUS_SERVER_IP,
            radius_secret=router.radius_secret,
            auth_port=settings.RADIUS_SERVER_AUTH_PORT,
            acct_port=settings.RADIUS_SERVER_ACCT_PORT,
        )
        router.radius_configured = True
        db.commit()
        db.refresh(router)
        logger.info(
            "Router %s (%s): RADIUS NAS and MikroTik RADIUS client configured at %s",
            router.id, router.name, vpn_ip,
        )
    except Exception as e:
        logger.warning(
            "Router %s (%s): RADIUS setup failed: %s\n%s",
            router.id, router.name, e, traceback.format_exc(),
        )
    finally:
        if connection:
            try:
                pool = connection.get("pool")
                if pool:
                    pool.disconnect()
            except Exception:
                pass


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
        router_info = parse_openvpn_status_log()  # Returns Dict[str, Tuple[str, Optional[str]]]
        
        for router in routers:
            try:
                router_data = router_info.get(router.vpn_username)
                vpn_ip = router_data[0] if router_data else None
                connected_since_str = router_data[1] if router_data and len(router_data) > 1 else None
                mikrotik_api_accessible = False
                final_status = router.status

                if vpn_ip:
                    # Router is connected to VPN - always update last_seen to current time
                    if router.vpn_ip != vpn_ip:
                        # Update VPN IP and last_seen
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            vpn_ip=vpn_ip,
                            status=RouterStatus.VPN_CONNECTED
                        )
                    else:
                        # VPN IP hasn't changed, but router is still connected - update last_seen
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            update_last_seen=True
                        )

                    # Test MikroTik API connection (use the newly parsed vpn_ip)
                    if mikrotik_service.test_api_connection(vpn_ip, router.api_port):
                        mikrotik_api_accessible = True
                        final_status = RouterStatus.ONLINE.value
                        # API is accessible, router is online - update last_seen
                        if router.status != RouterStatus.ONLINE.value:
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                status=RouterStatus.ONLINE
                            )
                        else:
                            # Status already ONLINE, but still update last_seen
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                update_last_seen=True
                            )

                        # Phase 2: When router has vpn_ip and API is reachable, register NAS and auto-configure MikroTik RADIUS
                        radius_configured = getattr(router, "radius_configured", None)
                        radius_secret = getattr(router, "radius_secret", None)
                        radius_server_ip = getattr(settings, "RADIUS_SERVER_IP", None) or ""
                        if radius_secret and not radius_configured and radius_server_ip.strip():
                            _ensure_router_radius_setup(db, router, vpn_ip)
                    else:
                        mikrotik_api_accessible = False
                        final_status = RouterStatus.VPN_CONNECTED.value
                        # VPN connected but API not accessible
                        if router.status != RouterStatus.VPN_CONNECTED.value:
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                status=RouterStatus.VPN_CONNECTED
                            )
                        else:
                            # Status already VPN_CONNECTED, but still update last_seen
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                update_last_seen=True
                            )
                else:
                    final_status = RouterStatus.OFFLINE.value if router.status != RouterStatus.PENDING.value else RouterStatus.PENDING.value
                    # Router not in VPN log, mark as offline
                    if router.status != RouterStatus.PENDING.value:
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            status=RouterStatus.OFFLINE
                        )

                # Parse Connected Since timestamp if available
                connected_since_dt = None
                if connected_since_str:
                    cleaned_str = connected_since_str.strip()
                    # Skip invalid values like '0' which indicate no connection time
                    if cleaned_str and cleaned_str != '0':
                        try:
                            # OpenVPN format: "Mon Jan  1 12:00:00 2024" or "2024-01-01 12:00:00"
                            # Try parsing common OpenVPN timestamp formats
                            connected_since_dt = date_parser.parse(cleaned_str)
                        except Exception as e:
                            connected_since_dt = None

                # Record status history for this cycle
                # Refresh router to get latest status and vpn_ip
                db.refresh(router)
                
                # Determine last_seen based on status
                last_seen = None
                if final_status == RouterStatus.ONLINE.value:
                    # If status is online, set last_seen to current time
                    last_seen = datetime.now(timezone.utc)
                else:
                    # If status is not online, find the last history record where status was "online"
                    last_online_history = (
                        db.query(RouterStatusHistory)
                        .filter(
                            RouterStatusHistory.router_id == router.id,
                            RouterStatusHistory.status == RouterStatus.ONLINE.value
                        )
                        .order_by(RouterStatusHistory.recorded_at.desc())
                        .first()
                    )
                    if last_online_history and last_online_history.last_seen:
                        last_seen = last_online_history.last_seen
                    # If router has never been online, last_seen remains None
                
                status_history = RouterStatusHistory(
                    router_id=router.id,
                    status=router.status,
                    vpn_ip=router.vpn_ip,
                    api_port=router.api_port,
                    mikrotik_api_accessible=mikrotik_api_accessible,
                    connected_since=connected_since_dt,
                    last_seen=last_seen
                )
                db.add(status_history)

            except Exception as e:
                continue
        
        # Commit all status history records
        try:
            db.commit()
        except Exception as e:
            db.rollback()

    except Exception as e:
        pass
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
                # Run every 10 seconds
                await asyncio.sleep(10)
            except Exception as e:
                await asyncio.sleep(60)

    # Run in background
    asyncio.create_task(monitor_loop())
