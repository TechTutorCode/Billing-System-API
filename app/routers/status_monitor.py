"""Background task for monitoring router status from OpenVPN logs."""

import logging
import re
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


def parse_openvpn_status_log() -> Dict[str, str]:
    """
    Parse OpenVPN status log to extract VPN IPs mapped to usernames.

    OpenVPN status log format:
    CLIENT_LIST: Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
    ROUTING_TABLE: Virtual Address,Common Name,Real Address,Last Ref

    Returns:
        Dictionary mapping vpn_username to vpn_ip
    """
    username_to_ip: Dict[str, str] = {}

    try:
        with open(OPENVPN_STATUS_LOG, "r") as f:
            content = f.read()

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

    except FileNotFoundError:
        logger.warning(f"OpenVPN status log not found at {OPENVPN_STATUS_LOG}")
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

