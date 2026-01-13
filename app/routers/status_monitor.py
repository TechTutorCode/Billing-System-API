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
    logger.info("=" * 80)
    logger.info("[MONITOR] parse_openvpn_status_log() CALLED")
    logger.info("=" * 80)
    
    username_to_ip: Dict[str, str] = {}

    try:
        # Read OpenVPN status log from host machine via SSH
        # Test SSH connection first
        test_cmd = _build_ssh_command("echo 'SSH_TEST_SUCCESS'")
        test_result = subprocess.run(test_cmd, capture_output=True, text=True, timeout=10, check=False)
        logger.info(f"[MONITOR] SSH connection test - Return code: {test_result.returncode}, Output: {test_result.stdout.strip()}")
        print(f"[MONITOR] SSH test: {test_result.stdout.strip()}")
        
        if test_result.returncode != 0:
            logger.error(f"[MONITOR] ❌ SSH connection test failed!")
            print(f"[MONITOR] ❌ SSH connection test failed: {test_result.stderr}")
            return username_to_ip
        
        # Use sudo to read the file (it's in /var/log/ which may require root)
        remote_command = f"sudo cat {OPENVPN_STATUS_LOG} 2>&1"
        ssh_cmd = _build_ssh_command(remote_command)
        logger.info(f"[MONITOR] Full SSH command: {' '.join(ssh_cmd[:5])}... {ssh_cmd[-2]} '<command>'")
        logger.info(f"[MONITOR] Executing SSH to read file: {OPENVPN_STATUS_LOG}")
        print(f"[MONITOR] Executing SSH to read: {OPENVPN_STATUS_LOG}")
        print(f"[MONITOR] SSH Host: {settings.SSH_HOST}, User: {settings.SSH_USER}")
        print(f"[MONITOR] File path: {OPENVPN_STATUS_LOG}")
        
        logger.info(f"[MONITOR] ========================================")
        logger.info(f"[MONITOR] EXECUTING SSH COMMAND TO READ FILE")
        logger.info(f"[MONITOR] File: {OPENVPN_STATUS_LOG}")
        logger.info(f"[MONITOR] Host: {settings.SSH_HOST}")
        logger.info(f"[MONITOR] User: {settings.SSH_USER}")
        logger.info(f"[MONITOR] Command: cat {OPENVPN_STATUS_LOG}")
        logger.info(f"[MONITOR] ========================================")
        
        result = subprocess.run(
            ssh_cmd,
            capture_output=True,
            text=True,
            timeout=10,
            check=False
        )
        
        logger.info(f"[MONITOR] SSH COMMAND COMPLETED")
        logger.info(f"[MONITOR] Return Code: {result.returncode}")
        logger.info(f"[MONITOR] stdout length: {len(result.stdout)} chars")
        logger.info(f"[MONITOR] stderr length: {len(result.stderr)} chars")
        
        if result.stderr:
            logger.warning(f"[MONITOR] SSH stderr output: {result.stderr}")
        
        if result.returncode != 0:
            error_msg = result.stderr.strip() if result.stderr else result.stdout.strip() or "Unknown error"
            logger.error(f"[MONITOR] ❌ SSH COMMAND FAILED (return code: {result.returncode})")
            logger.error(f"[MONITOR] Error: {error_msg}")
            logger.error(f"[MONITOR] stdout: {result.stdout}")
            return username_to_ip
        
        content = result.stdout
        logger.info(f"[MONITOR] ✅ SSH COMMAND EXECUTED")
        logger.info(f"[MONITOR] Content length: {len(content)} characters")
        logger.info(f"[MONITOR] ========================================")
        logger.info(f"[MONITOR] RAW FILE CONTENT (PRINTING FULL CONTENT):")
        print(f"\n[MONITOR] ========== RAW CONTENT FROM SSH ==========")
        print(f"[MONITOR] Content length: {len(content)}")
        print(f"[MONITOR] Content:\n{content}")
        print(f"[MONITOR] ===========================================\n")
        logger.info(f"[MONITOR] RAW CONTENT:\n{content}")
        logger.info(f"[MONITOR] ========================================")
        
        # Check if content is empty or contains error
        if not content or len(content.strip()) == 0:
            logger.error(f"[MONITOR] ❌ CONTENT IS EMPTY! SSH returned no data!")
            print(f"[MONITOR] ❌ CONTENT IS EMPTY!")
            print(f"[MONITOR] SSH return code was: {result.returncode}")
            print(f"[MONITOR] SSH stderr: {result.stderr}")
            # Try to check if file exists with proper path
            check_cmd = _build_ssh_command(f"test -f {OPENVPN_STATUS_LOG} && echo 'FILE_EXISTS' || (echo 'FILE_NOT_FOUND' && ls -la /var/log/ | grep -i openvpn)")
            check_result = subprocess.run(check_cmd, capture_output=True, text=True, timeout=10, check=False)
            logger.error(f"[MONITOR] File existence check return code: {check_result.returncode}")
            logger.error(f"[MONITOR] File existence check output: {check_result.stdout}")
            logger.error(f"[MONITOR] File existence check error: {check_result.stderr}")
            print(f"[MONITOR] File check result: {check_result.stdout}")
            print(f"[MONITOR] File check stderr: {check_result.stderr}")
            
            # Also try to see what's in /var/log/ and check the actual file
            list_cmd = _build_ssh_command(f"ls -la /var/log/ | grep -i openvpn")
            list_result = subprocess.run(list_cmd, capture_output=True, text=True, timeout=10, check=False)
            print(f"[MONITOR] /var/log/ openvpn files: {list_result.stdout}")
            
            # Try reading with sudo in case of permissions
            sudo_cmd = _build_ssh_command(f"sudo cat {OPENVPN_STATUS_LOG} 2>&1")
            sudo_result = subprocess.run(sudo_cmd, capture_output=True, text=True, timeout=10, check=False)
            print(f"[MONITOR] Sudo cat result (return code {sudo_result.returncode}): {sudo_result.stdout[:200] if sudo_result.stdout else 'EMPTY'}")
            if sudo_result.stdout and len(sudo_result.stdout.strip()) > 0:
                logger.info(f"[MONITOR] ✅ Got content with sudo! Using it...")
                content = sudo_result.stdout
                # Continue with parsing instead of returning
            else:
                logger.error(f"[MONITOR] Sudo also returned empty: {sudo_result.stderr}")
                return username_to_ip
        
        # Check if file was not found (error message in content)
        if "No such file" in content or "cannot access" in content.lower() or "Permission denied" in content:
            logger.error(f"[MONITOR] ❌ FILE ERROR: {content}")
            print(f"[MONITOR] ❌ FILE ERROR: {content}")
            return username_to_ip
        
        # Check if file was not found
        if "FILE_NOT_FOUND" in content:
            logger.error(f"[MONITOR] ❌ FILE NOT FOUND at {OPENVPN_STATUS_LOG}")
            print(f"[MONITOR] ❌ FILE NOT FOUND at {OPENVPN_STATUS_LOG}")
            return username_to_ip

        # Parse ROUTING TABLE section to get Virtual Address mapped to Common Name
        # Format: Virtual Address,Common Name,Real Address,Last Ref
        # Note: The header is "ROUTING TABLE" (with space, not underscore)
        logger.info(f"[MONITOR] Searching for ROUTING TABLE section...")
        routing_section_match = re.search(
            r"ROUTING TABLE\s+(.*?)(?=GLOBAL STATS|END|$)",
            content,
            re.DOTALL
        )

        if routing_section_match:
            routing_content = routing_section_match.group(1).strip()
            logger.info(f"[MONITOR] Found ROUTING TABLE section ({len(routing_content)} characters)")
            logger.info(f"[MONITOR] ROUTING TABLE content:\n{routing_content}")
            
            routing_lines = routing_content.split("\n")
            logger.info(f"[MONITOR] Found {len(routing_lines)} lines in ROUTING TABLE")
            
            for i, line in enumerate(routing_lines):
                logger.debug(f"[MONITOR] Processing ROUTING TABLE line {i}: {line}")
                if not line.strip() or line.startswith("Virtual"):
                    logger.debug(f"[MONITOR] Skipping line (empty or header): {line}")
                    continue

                # Parse line: Virtual Address,Common Name,Real Address,Last Ref
                parts = line.split(",")
                logger.debug(f"[MONITOR] Split into {len(parts)} parts: {parts}")
                if len(parts) >= 2:
                    virtual_ip = parts[0].strip()
                    username = parts[1].strip()
                    logger.info(f"[MONITOR] Extracted - Username: '{username}', VPN IP: '{virtual_ip}'")
                    if username and virtual_ip:
                        username_to_ip[username] = virtual_ip
                        logger.info(f"[MONITOR] ✓ Found router {username} with VPN IP {virtual_ip}")
                    else:
                        logger.warning(f"[MONITOR] Skipping entry - username or IP is empty")
                else:
                    logger.warning(f"[MONITOR] Line has insufficient parts ({len(parts)} < 2): {line}")
        else:
            logger.error(f"[MONITOR] ❌ ROUTING TABLE section not found in content")
            print(f"[MONITOR] ❌ ROUTING TABLE section not found!")
            print(f"[MONITOR] Content length: {len(content)}")
            print(f"[MONITOR] Content preview:\n{content[:500]}")
            logger.error(f"[MONITOR] Content preview:\n{content[:1000]}")
            logger.error(f"[MONITOR] Full content:\n{content}")
            logger.error(f"[MONITOR] 'ROUTING' in content: {'ROUTING' in content}")
            logger.error(f"[MONITOR] 'TABLE' in content: {'TABLE' in content}")
            logger.error(f"[MONITOR] 'ROUTING TABLE' in content: {'ROUTING TABLE' in content}")

        # Also verify in CLIENT LIST that the router is actually connected
        # Note: The header is "OpenVPN CLIENT LIST" (with "OpenVPN" prefix)
        logger.info(f"[MONITOR] Searching for CLIENT LIST section...")
        client_section_match = re.search(
            r"OpenVPN CLIENT LIST\s+(.*?)(?=ROUTING TABLE|$)",
            content,
            re.DOTALL
        )

        if client_section_match:
            client_content = client_section_match.group(1).strip()
            logger.info(f"[MONITOR] Found OpenVPN CLIENT LIST section ({len(client_content)} characters)")
            logger.info(f"[MONITOR] CLIENT LIST content:\n{client_content}")
            
            connected_usernames = set()
            client_lines = client_content.split("\n")
            logger.info(f"[MONITOR] Found {len(client_lines)} lines in CLIENT LIST")
            
            for i, line in enumerate(client_lines):
                logger.debug(f"[MONITOR] Processing CLIENT LIST line {i}: {line}")
                # Skip header lines: "Updated,..." and "Common Name,..."
                if not line.strip() or line.startswith("Common") or line.startswith("Updated"):
                    logger.debug(f"[MONITOR] Skipping CLIENT LIST line (empty or header): {line}")
                    continue

                # Parse line: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
                parts = line.split(",")
                logger.debug(f"[MONITOR] CLIENT LIST split into {len(parts)} parts: {parts}")
                if len(parts) >= 1:
                    username = parts[0].strip()
                    if username:
                        connected_usernames.add(username)
                        logger.info(f"[MONITOR] ✓ Found connected username in CLIENT LIST: {username}")

            logger.info(f"[MONITOR] Total connected usernames in CLIENT LIST: {len(connected_usernames)}")
            logger.info(f"[MONITOR] Connected usernames: {connected_usernames}")
            logger.info(f"[MONITOR] Routers from ROUTING TABLE before filtering: {username_to_ip}")

            # Only keep routers that are in both CLIENT LIST and ROUTING TABLE
            username_to_ip = {
                username: ip 
                for username, ip in username_to_ip.items() 
                if username in connected_usernames
            }
            
            logger.info(f"[MONITOR] Routers after filtering (in both sections): {username_to_ip}")
        else:
            logger.error(f"[MONITOR] ❌ OpenVPN CLIENT LIST section not found in content")
            print(f"\n[MONITOR] ❌ OpenVPN CLIENT LIST section not found!")
            logger.error(f"[MONITOR] 'CLIENT' in content: {'CLIENT' in content}")
            logger.error(f"[MONITOR] 'OpenVPN' in content: {'OpenVPN' in content}")
            logger.error(f"[MONITOR] 'OpenVPN CLIENT LIST' in content: {'OpenVPN CLIENT LIST' in content}")
            logger.error(f"[MONITOR] Searching for 'CLIENT' in content: {'CLIENT' in content}")
            logger.error(f"[MONITOR] Searching for 'OpenVPN' in content: {'OpenVPN' in content}")

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
    print("\n" + "=" * 80)
    print("[MONITOR] ===== STARTING ROUTER STATUS MONITORING CYCLE =====")
    print("=" * 80 + "\n")
    logger.info("=" * 60)
    logger.info("Starting router status monitoring cycle")
    logger.info("=" * 60)
    
    db: Session = SessionLocal()
    try:
        # Get all active routers
        routers = db.query(Router).filter(Router.is_active == True).all()
        logger.info(f"Found {len(routers)} active router(s) in database")

        if not routers:
            print("[MONITOR] No active routers found, skipping status update")
            logger.info("No active routers found, skipping status update")
            return

        # Parse OpenVPN status log
        logger.info(f"Reading OpenVPN status log from host: {OPENVPN_STATUS_LOG}")
        username_to_ip = parse_openvpn_status_log()
        
        logger.info(f"Parsed {len(username_to_ip)} router(s) from OpenVPN status log")
        if username_to_ip:
            logger.info(f"Connected routers: {username_to_ip}")
        else:
            logger.warning("No routers found in OpenVPN status log")

        for router in routers:
            try:
                logger.info(f"Processing router: {router.vpn_username} (ID: {router.id})")
                logger.info(f"  Current status: {router.status}")
                logger.info(f"  Current VPN IP: {router.vpn_ip}")
                
                vpn_ip = username_to_ip.get(router.vpn_username)

                if vpn_ip:
                    logger.info(f"  ✓ Router found in VPN log with IP: {vpn_ip}")
                    # Router is connected to VPN - always update last_seen to current time
                    if router.vpn_ip != vpn_ip:
                        logger.info(f"  → Updating VPN IP from {router.vpn_ip} to {vpn_ip}")
                        # Update VPN IP and last_seen
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            vpn_ip=vpn_ip,
                            status=RouterStatus.VPN_CONNECTED
                        )
                        logger.info(f"  → Status updated to: VPN_CONNECTED")
                    else:
                        # VPN IP hasn't changed, but router is still connected - update last_seen
                        logger.info(f"  → Router still connected, updating last_seen timestamp")
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            update_last_seen=True
                        )

                    # Test MikroTik API connection (use the newly parsed vpn_ip)
                    logger.info(f"  → Testing MikroTik API connection at {vpn_ip}:{router.api_port}")
                    if mikrotik_service.test_api_connection(vpn_ip, router.api_port):
                        logger.info(f"  ✓ MikroTik API is accessible")
                        # API is accessible, router is online - update last_seen
                        if router.status != RouterStatus.ONLINE.value:
                            logger.info(f"  → Updating status from {router.status} to ONLINE")
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                status=RouterStatus.ONLINE
                            )
                        else:
                            # Status already ONLINE, but still update last_seen
                            logger.info(f"  → Status already ONLINE, updating last_seen timestamp")
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                update_last_seen=True
                            )
                    else:
                        logger.info(f"  ✗ MikroTik API not accessible")
                        # VPN connected but API not accessible
                        if router.status != RouterStatus.VPN_CONNECTED.value:
                            logger.info(f"  → Updating status from {router.status} to VPN_CONNECTED")
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                status=RouterStatus.VPN_CONNECTED
                            )
                        else:
                            # Status already VPN_CONNECTED, but still update last_seen
                            logger.info(f"  → Status already VPN_CONNECTED, updating last_seen timestamp")
                            router_service.update_router_status(
                                db=db,
                                router=router,
                                update_last_seen=True
                            )
                else:
                    logger.info(f"  ✗ Router NOT found in VPN log")
                    # Router not in VPN log, mark as offline
                    if router.status != RouterStatus.PENDING.value:
                        logger.info(f"  → Updating status from {router.status} to OFFLINE")
                        router_service.update_router_status(
                            db=db,
                            router=router,
                            status=RouterStatus.OFFLINE
                        )
                    else:
                        logger.info(f"  → Router is still PENDING, keeping status as is")

            except Exception as e:
                logger.error(f"Error updating status for router {router.id}: {str(e)}", exc_info=True)
                continue
        
        logger.info("=" * 60)
        logger.info("Router status monitoring cycle completed")
        logger.info("=" * 60)

    except Exception as e:
        logger.error(f"Error in router status monitor: {str(e)}", exc_info=True)
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

