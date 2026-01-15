"""Background task for monitoring and expiring subscriptions."""

import asyncio
import logging
from datetime import datetime, timezone

from app.database import SessionLocal
from app.subscriptions.service import subscription_service

logger = logging.getLogger(__name__)


def expire_subscriptions_task():
    """
    Background task to expire subscriptions that have passed their end_at date.

    This should be called periodically (e.g., every minute) by a scheduler.
    """
    db = SessionLocal()
    try:
        expired_count = subscription_service.expire_subscriptions(db)
        if expired_count > 0:
            logger.info(f"Expired {expired_count} subscription(s)")
        return expired_count
    except Exception as e:
        logger.error(f"Error in subscription expiry task: {str(e)}", exc_info=True)
        return 0
    finally:
        db.close()


async def start_expiry_monitor():
    """
    Start background task to monitor and expire subscriptions.

    Runs every minute to check for expired subscriptions.
    """
    logger.info("Starting subscription expiry monitor. Will run every 60 seconds.")
    
    async def monitor_loop():
        """Background task loop for expiring subscriptions."""
        while True:
            try:
                print("[EXPIRY] Starting subscription expiry check...")
                expired_count = expire_subscriptions_task()
                if expired_count > 0:
                    print(f"[EXPIRY] Expired {expired_count} subscription(s)")
                else:
                    print("[EXPIRY] No subscriptions to expire")
                
                # Run every 60 seconds (1 minute)
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Error in subscription expiry monitor loop: {str(e)}", exc_info=True)
                print(f"[EXPIRY] ❌ Error in expiry monitor: {str(e)}")
                # Wait 60 seconds before retrying
                await asyncio.sleep(60)
    
    # Start the background task
    asyncio.create_task(monitor_loop())

