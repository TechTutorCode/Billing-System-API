"""Subscription business logic services."""

import logging
from datetime import datetime, timedelta, timezone
from typing import List, Optional, Tuple
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_

from app.customers.models import Customer
from app.packages.models import ServicePackage
from app.routers.models import Router
from app.routers.mikrotik_service import mikrotik_service
from app.subscriptions.mikrotik_actions import subscription_mikrotik_actions
from app.subscriptions.models import Subscription, SubscriptionStatus, SubscriptionPackageType
from app.packages.types import ValidityUnit

logger = logging.getLogger(__name__)


class SubscriptionService:
    """Service for subscription-related operations."""

    @staticmethod
    def calculate_end_date(start_date: datetime, validity_value: int, validity_unit: str) -> datetime:
        """
        Calculate end date based on validity.

        Args:
            start_date: Start date
            validity_value: Validity value
            validity_unit: Validity unit (minutes, hours, days)

        Returns:
            End date
        """
        if validity_unit == ValidityUnit.MINUTES.value:
            return start_date + timedelta(minutes=validity_value)
        elif validity_unit == ValidityUnit.HOURS.value:
            return start_date + timedelta(hours=validity_value)
        elif validity_unit == ValidityUnit.DAYS.value:
            return start_date + timedelta(days=validity_value)
        else:
            raise ValueError(f"Invalid validity unit: {validity_unit}")

    @staticmethod
    def create_subscription(
        db: Session,
        isp_id: UUID,
        subscription_data: dict
    ) -> Subscription:
        """
        Create a new subscription (pending status).

        Args:
            db: Database session
            isp_id: ISP ID
            subscription_data: Subscription data dictionary

        Returns:
            Subscription instance

        Raises:
            HTTPException: If validation fails
        """
        customer_id = subscription_data["customer_id"]
        router_id = subscription_data["router_id"]
        package_id = subscription_data["package_id"]
        username = subscription_data["username"]

        # Verify customer exists and belongs to ISP
        customer = (
            db.query(Customer)
            .filter(Customer.id == customer_id, Customer.isp_id == isp_id)
            .first()
        )
        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found or does not belong to you"
            )

        # Verify router exists and belongs to ISP
        router = (
            db.query(Router)
            .filter(Router.id == router_id, Router.isp_id == isp_id, Router.is_active == True)
            .first()
        )
        if not router:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Router not found or does not belong to you"
            )

        # Verify package exists and belongs to router
        package = (
            db.query(ServicePackage)
            .filter(
                ServicePackage.id == package_id,
                ServicePackage.router_id == router_id,
                ServicePackage.is_active == True
            )
            .first()
        )
        if not package:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package not found or does not belong to this router"
            )

        # Get package type
        from app.packages.models import PackageType
        package_type_obj = db.query(PackageType).filter(PackageType.id == package.package_type_id).first()
        if not package_type_obj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Package type not found"
            )
        package_type_name = package_type_obj.name.lower()

        # Validate package type (only PPPoE and Static allowed)
        if package_type_name not in ["pppoe", "static"]:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Package type '{package_type_name}' is not supported for subscriptions. Only PPPoE and Static are allowed."
            )

        # Validate package type requirements
        if package_type_name == "pppoe":
            if not subscription_data.get("password"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Password is required for PPPoE subscriptions"
                )
        elif package_type_name == "static":
            if not subscription_data.get("ip_address"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="IP address is required for Static IP subscriptions"
                )

        # Check username uniqueness per router
        existing = (
            db.query(Subscription)
            .filter(
                Subscription.router_id == router_id,
                Subscription.username == username
            )
            .first()
        )
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Username '{username}' already exists on this router"
            )

        # Check for overlapping active subscriptions (same customer + router)
        overlapping = (
            db.query(Subscription)
            .filter(
                Subscription.customer_id == customer_id,
                Subscription.router_id == router_id,
                Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.SUSPENDED.value])
            )
            .first()
        )
        if overlapping:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer already has an active or suspended subscription on this router"
            )

        # Create subscription (pending status)
        subscription = Subscription(
            isp_id=isp_id,
            customer_id=customer_id,
            router_id=router_id,
            package_id=package_id,
            package_type=package_type_name,
            username=username,
            password=subscription_data.get("password"),
            ip_address=subscription_data.get("ip_address"),
            status=SubscriptionStatus.PENDING.value
        )
        db.add(subscription)
        db.commit()
        db.refresh(subscription)

        logger.info(f"Created subscription {subscription.id} for customer {customer_id} on router {router_id}")
        return subscription

    @staticmethod
    def get_subscriptions(
        db: Session,
        isp_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        customer_id: Optional[UUID] = None,
        router_id: Optional[UUID] = None
    ) -> Tuple[List[Subscription], int]:
        """
        Get subscriptions with pagination and filters.

        Args:
            db: Database session
            isp_id: ISP ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Filter by status
            customer_id: Filter by customer ID
            router_id: Filter by router ID

        Returns:
            Tuple of (list of subscriptions, total count)
        """
        query = db.query(Subscription).filter(Subscription.isp_id == isp_id)

        if status_filter:
            query = query.filter(Subscription.status == status_filter.lower())

        if customer_id:
            query = query.filter(Subscription.customer_id == customer_id)

        if router_id:
            query = query.filter(Subscription.router_id == router_id)

        total = query.count()
        subscriptions = query.order_by(Subscription.created_at.desc()).offset(skip).limit(limit).all()

        return subscriptions, total

    @staticmethod
    def get_subscription_by_id(
        db: Session,
        subscription_id: UUID,
        isp_id: UUID
    ) -> Subscription:
        """
        Get subscription by ID.

        Args:
            db: Database session
            subscription_id: Subscription ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            Subscription instance

        Raises:
            HTTPException: If subscription not found
        """
        subscription = (
            db.query(Subscription)
            .filter(Subscription.id == subscription_id, Subscription.isp_id == isp_id)
            .first()
        )

        if not subscription:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Subscription not found or does not belong to you"
            )

        return subscription

    @staticmethod
    def activate_subscription(
        db: Session,
        subscription_id: UUID,
        isp_id: UUID,
        api_password: Optional[str] = None
    ) -> Subscription:
        """
        Activate subscription on MikroTik router.

        Args:
            db: Database session
            subscription_id: Subscription ID
            isp_id: ISP ID (for ownership verification)
            api_password: MikroTik API password (if not stored)

        Returns:
            Updated Subscription instance

        Raises:
            HTTPException: If activation fails
        """
        subscription = SubscriptionService.get_subscription_by_id(db, subscription_id, isp_id)

        if subscription.status != SubscriptionStatus.PENDING.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot activate subscription with status '{subscription.status}'. Only pending subscriptions can be activated."
            )

        # Load related objects
        router = db.query(Router).filter(Router.id == subscription.router_id).first()
        if not router:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Router not found")

        package = db.query(ServicePackage).filter(ServicePackage.id == subscription.package_id).first()
        if not package:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Package not found")

        # Verify router has VPN IP
        if not router.vpn_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router VPN IP not available. Router must be connected via VPN."
            )

        # Get package profile name
        if not package.mikrotik_profile_name:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Package has not been synced to MikroTik. Please sync the package first."
            )

        # Get API credentials
        api_username = router.mikrotik_api_username or "admin"
        if api_password:
            api_password_plain = api_password
        elif router.mikrotik_api_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password required. Please provide it in the request body."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password not configured. Please provide it in the request body."
            )

        connection = None
        try:
            # Connect to MikroTik
            connection = mikrotik_service.connect(
                host=router.vpn_ip,
                username=api_username,
                password=api_password_plain,
                port=router.api_port
            )

            # Activate based on package type
            if subscription.package_type == SubscriptionPackageType.PPPOE.value:
                # Check if secret already exists
                if subscription_mikrotik_actions.check_pppoe_secret_exists(connection, subscription.username):
                    logger.warning(f"PPPoE secret '{subscription.username}' already exists, skipping creation")
                else:
                    # Create PPPoE secret
                    subscription_mikrotik_actions.create_pppoe_secret(
                        connection_dict=connection,
                        username=subscription.username,
                        password=subscription.password,
                        profile_name=package.mikrotik_profile_name
                    )

            elif subscription.package_type == SubscriptionPackageType.STATIC.value:
                # Check if queue already exists
                if subscription_mikrotik_actions.check_static_queue_exists(connection, subscription.username):
                    logger.warning(f"Static queue '{subscription.username}' already exists, skipping creation")
                else:
                    # Create static queue
                    subscription_mikrotik_actions.create_static_queue(
                        connection_dict=connection,
                        queue_name=subscription.username,
                        ip_address=subscription.ip_address,
                        download_speed=package.download_speed,
                        upload_speed=package.upload_speed
                    )

            # Calculate dates
            start_at = datetime.now(timezone.utc)
            end_at = SubscriptionService.calculate_end_date(
                start_at,
                package.validity_value,
                package.validity_unit
            )

            # Update subscription
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.start_at = start_at
            subscription.end_at = end_at
            subscription.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(subscription)

            logger.info(f"Activated subscription {subscription_id}")
            return subscription

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to activate subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to activate subscription: {str(e)}"
            )
        finally:
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")

    @staticmethod
    def suspend_subscription(
        db: Session,
        subscription_id: UUID,
        isp_id: UUID,
        api_password: Optional[str] = None
    ) -> Subscription:
        """
        Suspend subscription (disable on MikroTik).

        Args:
            db: Database session
            subscription_id: Subscription ID
            isp_id: ISP ID (for ownership verification)
            api_password: MikroTik API password (if not stored)

        Returns:
            Updated Subscription instance

        Raises:
            HTTPException: If suspension fails
        """
        subscription = SubscriptionService.get_subscription_by_id(db, subscription_id, isp_id)

        if subscription.status != SubscriptionStatus.ACTIVE.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot suspend subscription with status '{subscription.status}'. Only active subscriptions can be suspended."
            )

        # Load router
        router = db.query(Router).filter(Router.id == subscription.router_id).first()
        if not router or not router.vpn_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router not available"
            )

        # Get API credentials
        api_username = router.mikrotik_api_username or "admin"
        if api_password:
            api_password_plain = api_password
        elif router.mikrotik_api_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password required. Please provide it in the request body."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password not configured. Please provide it in the request body."
            )

        connection = None
        try:
            # Connect to MikroTik
            connection = mikrotik_service.connect(
                host=router.vpn_ip,
                username=api_username,
                password=api_password_plain,
                port=router.api_port
            )

            # Disable based on package type
            if subscription.package_type == SubscriptionPackageType.PPPOE.value:
                subscription_mikrotik_actions.disable_pppoe_secret(connection, subscription.username)
            elif subscription.package_type == SubscriptionPackageType.STATIC.value:
                subscription_mikrotik_actions.disable_static_queue(connection, subscription.username)

            # Update subscription
            subscription.status = SubscriptionStatus.SUSPENDED.value
            subscription.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(subscription)

            logger.info(f"Suspended subscription {subscription_id}")
            return subscription

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to suspend subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to suspend subscription: {str(e)}"
            )
        finally:
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")

    @staticmethod
    def resume_subscription(
        db: Session,
        subscription_id: UUID,
        isp_id: UUID,
        api_password: Optional[str] = None
    ) -> Subscription:
        """
        Resume subscription (re-enable on MikroTik).

        Args:
            db: Database session
            subscription_id: Subscription ID
            isp_id: ISP ID (for ownership verification)
            api_password: MikroTik API password (if not stored)

        Returns:
            Updated Subscription instance

        Raises:
            HTTPException: If resumption fails
        """
        subscription = SubscriptionService.get_subscription_by_id(db, subscription_id, isp_id)

        if subscription.status != SubscriptionStatus.SUSPENDED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Cannot resume subscription with status '{subscription.status}'. Only suspended subscriptions can be resumed."
            )

        # Load router
        router = db.query(Router).filter(Router.id == subscription.router_id).first()
        if not router or not router.vpn_ip:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Router not available"
            )

        # Get API credentials
        api_username = router.mikrotik_api_username or "admin"
        if api_password:
            api_password_plain = api_password
        elif router.mikrotik_api_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password required. Please provide it in the request body."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password not configured. Please provide it in the request body."
            )

        connection = None
        try:
            # Connect to MikroTik
            connection = mikrotik_service.connect(
                host=router.vpn_ip,
                username=api_username,
                password=api_password_plain,
                port=router.api_port
            )

            # Enable based on package type
            if subscription.package_type == SubscriptionPackageType.PPPOE.value:
                subscription_mikrotik_actions.enable_pppoe_secret(connection, subscription.username)
            elif subscription.package_type == SubscriptionPackageType.STATIC.value:
                subscription_mikrotik_actions.enable_static_queue(connection, subscription.username)

            # Update subscription
            subscription.status = SubscriptionStatus.ACTIVE.value
            subscription.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(subscription)

            logger.info(f"Resumed subscription {subscription_id}")
            return subscription

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to resume subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to resume subscription: {str(e)}"
            )
        finally:
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")

    @staticmethod
    def terminate_subscription(
        db: Session,
        subscription_id: UUID,
        isp_id: UUID,
        api_password: Optional[str] = None
    ) -> Subscription:
        """
        Terminate subscription (remove from MikroTik).

        Args:
            db: Database session
            subscription_id: Subscription ID
            isp_id: ISP ID (for ownership verification)
            api_password: MikroTik API password (if not stored)

        Returns:
            Updated Subscription instance

        Raises:
            HTTPException: If termination fails
        """
        subscription = SubscriptionService.get_subscription_by_id(db, subscription_id, isp_id)

        if subscription.status == SubscriptionStatus.TERMINATED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Subscription is already terminated"
            )

        # Load router
        router = db.query(Router).filter(Router.id == subscription.router_id).first()
        if not router or not router.vpn_ip:
            # If router not available, just mark as terminated
            logger.warning(f"Router not available for subscription {subscription_id}, marking as terminated")
            subscription.status = SubscriptionStatus.TERMINATED.value
            subscription.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(subscription)
            return subscription

        # Get API credentials
        api_username = router.mikrotik_api_username or "admin"
        if api_password:
            api_password_plain = api_password
        elif router.mikrotik_api_password_encrypted:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password required. Please provide it in the request body."
            )
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="MikroTik API password not configured. Please provide it in the request body."
            )

        connection = None
        try:
            # Connect to MikroTik
            connection = mikrotik_service.connect(
                host=router.vpn_ip,
                username=api_username,
                password=api_password_plain,
                port=router.api_port
            )

            # Remove based on package type
            if subscription.package_type == SubscriptionPackageType.PPPOE.value:
                subscription_mikrotik_actions.remove_pppoe_secret(connection, subscription.username)
            elif subscription.package_type == SubscriptionPackageType.STATIC.value:
                subscription_mikrotik_actions.remove_static_queue(connection, subscription.username)

            # Update subscription
            subscription.status = SubscriptionStatus.TERMINATED.value
            subscription.updated_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(subscription)

            logger.info(f"Terminated subscription {subscription_id}")
            return subscription

        except HTTPException:
            db.rollback()
            raise
        except Exception as e:
            db.rollback()
            logger.error(f"Failed to terminate subscription: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to terminate subscription: {str(e)}"
            )
        finally:
            if connection:
                try:
                    connection_pool = connection.get("pool")
                    if connection_pool:
                        connection_pool.disconnect()
                except Exception as e:
                    logger.warning(f"Error closing MikroTik connection: {str(e)}")

    @staticmethod
    def expire_subscriptions(db: Session) -> int:
        """
        Expire subscriptions that have passed their end_at date.

        This should be called by a background task.

        Args:
            db: Database session

        Returns:
            Number of subscriptions expired
        """
        now = datetime.now(timezone.utc)
        
        # Find subscriptions that should be expired
        expired_subscriptions = (
            db.query(Subscription)
            .filter(
                Subscription.status.in_([SubscriptionStatus.ACTIVE.value, SubscriptionStatus.SUSPENDED.value]),
                Subscription.end_at < now
            )
            .all()
        )

        expired_count = 0
        for subscription in expired_subscriptions:
            try:
                # Load router
                router = db.query(Router).filter(Router.id == subscription.router_id).first()
                
                if router and router.vpn_ip:
                    # Get API credentials
                    api_username = router.mikrotik_api_username or "admin"
                    # For background tasks, we can't prompt for password
                    # Skip if password not available
                    if not router.mikrotik_api_password_encrypted:
                        logger.warning(f"Cannot expire subscription {subscription.id}: API password not configured")
                        continue
                    
                    # Note: In production, you should decrypt the password here
                    # For now, skip if password is encrypted (can't decrypt bcrypt)
                    logger.warning(f"Cannot expire subscription {subscription.id}: API password needs to be decrypted")
                    continue

                    connection = None
                    try:
                        # Connect to MikroTik
                        connection = mikrotik_service.connect(
                            host=router.vpn_ip,
                            username=api_username,
                            password=api_password_plain,
                            port=router.api_port
                        )

                        # Disable based on package type
                        if subscription.package_type == SubscriptionPackageType.PPPOE.value:
                            subscription_mikrotik_actions.disable_pppoe_secret(connection, subscription.username)
                        elif subscription.package_type == SubscriptionPackageType.STATIC.value:
                            subscription_mikrotik_actions.disable_static_queue(connection, subscription.username)

                    except Exception as e:
                        logger.error(f"Failed to disable subscription {subscription.id} on router: {str(e)}")
                        # Continue to mark as expired even if router operation fails
                    finally:
                        if connection:
                            try:
                                connection_pool = connection.get("pool")
                                if connection_pool:
                                    connection_pool.disconnect()
                            except Exception:
                                pass

                # Mark as expired
                subscription.status = SubscriptionStatus.EXPIRED.value
                subscription.updated_at = datetime.now(timezone.utc)
                expired_count += 1

            except Exception as e:
                logger.error(f"Error expiring subscription {subscription.id}: {str(e)}")
                continue

        if expired_count > 0:
            db.commit()
            logger.info(f"Expired {expired_count} subscription(s)")

        return expired_count


# Global instance
subscription_service = SubscriptionService()

