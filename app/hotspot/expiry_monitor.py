"""Background task to monitor and expire hotspot vouchers."""

import asyncio
import logging

from app.database import SessionLocal
from app.hotspot.service import hotspot_service

logger = logging.getLogger(__name__)


async def start_voucher_expiry_monitor():
    """
    Start background task to monitor and expire hotspot vouchers.

    This task runs every 5 minutes to check for expired vouchers
    and disable them on MikroTik routers.
    """
    logger.info("Starting hotspot voucher expiry monitor...")

    async def monitor_loop():
        """Background task loop to expire vouchers."""
        while True:
            try:
                db = SessionLocal()
                try:
                    expired_count = hotspot_service.expire_vouchers(db=db)
                    if expired_count > 0:
                        logger.info(f"Expired {expired_count} hotspot voucher(s)")
                except Exception as e:
                    logger.error(f"Error in voucher expiry monitor: {str(e)}", exc_info=True)
                finally:
                    db.close()

                # Run every 5 minutes
                await asyncio.sleep(300)
            except Exception as e:
                logger.error(f"Error in voucher expiry monitor loop: {str(e)}", exc_info=True)
                await asyncio.sleep(60)  # Wait 1 minute before retrying on error

    # Start the background task
    asyncio.create_task(monitor_loop())
    logger.info("Hotspot voucher expiry monitor started successfully")
