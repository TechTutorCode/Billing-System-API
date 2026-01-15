"""MikroTik actions for subscription management."""

import logging
from typing import Optional

from fastapi import HTTPException, status

from app.routers.mikrotik_service import mikrotik_service
from app.routers.models import Router

logger = logging.getLogger(__name__)


class SubscriptionMikroTikActions:
    """MikroTik actions for subscription operations."""

    @staticmethod
    def create_pppoe_secret(
        connection_dict,
        username: str,
        password: str,
        profile_name: str
    ) -> None:
        """
        Create PPPoE secret on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            username: PPPoE username
            password: PPPoE password
            profile_name: Profile name to assign

        Raises:
            HTTPException: If creation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Creating PPPoE secret '{username}' with profile '{profile_name}'")
            resource = api.get_resource("/ppp/secret")
            resource.add(
                name=username,
                password=password,
                profile=profile_name,
                service="pppoe",
                disabled="false"
            )
            logger.info(f"Successfully created PPPoE secret '{username}'")
        except Exception as e:
            logger.error(f"Failed to create PPPoE secret: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create PPPoE secret on router: {str(e)}"
            )

    @staticmethod
    def check_pppoe_secret_exists(
        connection_dict,
        username: str
    ) -> bool:
        """
        Check if PPPoE secret exists on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            username: PPPoE username

        Returns:
            True if secret exists, False otherwise
        """
        try:
            api = connection_dict["api"]
            resource = api.get_resource("/ppp/secret")
            secrets = resource.get(name=username)
            exists = len(secrets) > 0
            logger.info(f"PPPoE secret '{username}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking PPPoE secret existence: {str(e)}")
            return False

    @staticmethod
    def enable_pppoe_secret(
        connection_dict,
        username: str
    ) -> None:
        """
        Enable PPPoE secret on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            username: PPPoE username

        Raises:
            HTTPException: If operation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Enabling PPPoE secret '{username}'")
            resource = api.get_resource("/ppp/secret")
            secret = resource.get(name=username)
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"PPPoE secret '{username}' not found on router"
                )
            resource.set(id=secret[0]["id"], disabled="false")
            logger.info(f"Successfully enabled PPPoE secret '{username}'")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to enable PPPoE secret: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enable PPPoE secret: {str(e)}"
            )

    @staticmethod
    def disable_pppoe_secret(
        connection_dict,
        username: str
    ) -> None:
        """
        Disable PPPoE secret on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            username: PPPoE username

        Raises:
            HTTPException: If operation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Disabling PPPoE secret '{username}'")
            resource = api.get_resource("/ppp/secret")
            secret = resource.get(name=username)
            if not secret:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"PPPoE secret '{username}' not found on router"
                )
            resource.set(id=secret[0]["id"], disabled="true")
            logger.info(f"Successfully disabled PPPoE secret '{username}'")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to disable PPPoE secret: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to disable PPPoE secret: {str(e)}"
            )

    @staticmethod
    def remove_pppoe_secret(
        connection_dict,
        username: str
    ) -> None:
        """
        Remove PPPoE secret from MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            username: PPPoE username

        Raises:
            HTTPException: If removal fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Removing PPPoE secret '{username}'")
            resource = api.get_resource("/ppp/secret")
            secret = resource.get(name=username)
            if not secret:
                logger.warning(f"PPPoE secret '{username}' not found, skipping removal")
                return
            resource.remove(id=secret[0]["id"])
            logger.info(f"Successfully removed PPPoE secret '{username}'")
        except Exception as e:
            logger.error(f"Failed to remove PPPoE secret: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove PPPoE secret: {str(e)}"
            )

    @staticmethod
    def create_static_queue(
        connection_dict,
        queue_name: str,
        ip_address: str,
        download_speed: int,
        upload_speed: int
    ) -> None:
        """
        Create simple queue for static IP subscription.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name (usually username)
            ip_address: Static IP address
            download_speed: Download speed in Mbps
            upload_speed: Upload speed in Mbps

        Raises:
            HTTPException: If creation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Creating static queue '{queue_name}' for IP {ip_address} with limit {download_speed}M/{upload_speed}M")
            resource = api.get_resource("/queue/simple")
            resource.add(
                name=queue_name,
                target=ip_address,
                max_limit=f"{download_speed}M/{upload_speed}M",
                disabled="false"
            )
            logger.info(f"Successfully created static queue '{queue_name}'")
        except Exception as e:
            logger.error(f"Failed to create static queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to create static queue on router: {str(e)}"
            )

    @staticmethod
    def check_static_queue_exists(
        connection_dict,
        queue_name: str
    ) -> bool:
        """
        Check if static queue exists on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name

        Returns:
            True if queue exists, False otherwise
        """
        try:
            api = connection_dict["api"]
            resource = api.get_resource("/queue/simple")
            queues = resource.get(name=queue_name)
            exists = len(queues) > 0
            logger.info(f"Static queue '{queue_name}' exists: {exists}")
            return exists
        except Exception as e:
            logger.error(f"Error checking static queue existence: {str(e)}")
            return False

    @staticmethod
    def enable_static_queue(
        connection_dict,
        queue_name: str
    ) -> None:
        """
        Enable static queue on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name

        Raises:
            HTTPException: If operation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Enabling static queue '{queue_name}'")
            resource = api.get_resource("/queue/simple")
            queue = resource.get(name=queue_name)
            if not queue:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Static queue '{queue_name}' not found on router"
                )
            resource.set(id=queue[0]["id"], disabled="false")
            logger.info(f"Successfully enabled static queue '{queue_name}'")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to enable static queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to enable static queue: {str(e)}"
            )

    @staticmethod
    def disable_static_queue(
        connection_dict,
        queue_name: str
    ) -> None:
        """
        Disable static queue on MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name

        Raises:
            HTTPException: If operation fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Disabling static queue '{queue_name}'")
            resource = api.get_resource("/queue/simple")
            queue = resource.get(name=queue_name)
            if not queue:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"Static queue '{queue_name}' not found on router"
                )
            resource.set(id=queue[0]["id"], disabled="true")
            logger.info(f"Successfully disabled static queue '{queue_name}'")
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Failed to disable static queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to disable static queue: {str(e)}"
            )

    @staticmethod
    def remove_static_queue(
        connection_dict,
        queue_name: str
    ) -> None:
        """
        Remove static queue from MikroTik router.

        Args:
            connection_dict: Dictionary with 'pool' and 'api' keys from connect()
            queue_name: Queue name

        Raises:
            HTTPException: If removal fails
        """
        try:
            api = connection_dict["api"]
            logger.info(f"Removing static queue '{queue_name}'")
            resource = api.get_resource("/queue/simple")
            queue = resource.get(name=queue_name)
            if not queue:
                logger.warning(f"Static queue '{queue_name}' not found, skipping removal")
                return
            resource.remove(id=queue[0]["id"])
            logger.info(f"Successfully removed static queue '{queue_name}'")
        except Exception as e:
            logger.error(f"Failed to remove static queue: {str(e)}")
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to remove static queue: {str(e)}"
            )


# Global instance
subscription_mikrotik_actions = SubscriptionMikroTikActions()

