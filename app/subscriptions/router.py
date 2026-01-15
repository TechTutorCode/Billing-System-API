"""Subscription API routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_isp
from app.database import get_db
from app.isps.models import ISPDetails
from app.subscriptions.schemas import (
    SubscriptionActionRequest,
    SubscriptionActionResponse,
    SubscriptionCreate,
    SubscriptionResponse,
    SubscriptionUpdate,
)
from app.subscriptions.service import subscription_service

router = APIRouter(prefix="/api/subscriptions", tags=["Subscriptions"])


@router.post(
    "/",
    response_model=SubscriptionResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Subscription",
    description="Create a new subscription (pending status). Does NOT activate on MikroTik."
)
def create_subscription(
    request: SubscriptionCreate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Create a new subscription.

    This endpoint:
    - Creates subscription with 'pending' status
    - Validates username uniqueness per router
    - Validates package type requirements (PPPoE needs password, Static needs IP)
    - Prevents overlapping active subscriptions
    - Does NOT create user on MikroTik (use activate endpoint)
    - Requires valid JWT access token
    """
    try:
        subscription = subscription_service.create_subscription(
            db=db,
            isp_id=current_isp.id,
            subscription_data=request.model_dump(exclude_none=True)
        )

        return SubscriptionResponse(
            id=str(subscription.id),
            isp_id=str(subscription.isp_id),
            customer_id=str(subscription.customer_id),
            router_id=str(subscription.router_id),
            package_id=str(subscription.package_id),
            package_type=subscription.package_type,
            username=subscription.username,
            password=subscription.password,  # Note: In production, consider masking this
            ip_address=subscription.ip_address,
            status=subscription.status,
            start_at=subscription.start_at.isoformat() if subscription.start_at else None,
            end_at=subscription.end_at.isoformat() if subscription.end_at else None,
            created_at=subscription.created_at.isoformat(),
            updated_at=subscription.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create subscription: {str(e)}"
        )


@router.get(
    "/",
    response_model=List[SubscriptionResponse],
    summary="List Subscriptions",
    description="Get list of subscriptions with pagination and filters."
)
def list_subscriptions(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[str] = Query(default=None, description="Filter by status"),
    customer_id: Optional[str] = Query(default=None, description="Filter by customer ID"),
    router_id: Optional[str] = Query(default=None, description="Filter by router ID"),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    List subscriptions with pagination and filters.

    This endpoint:
    - Returns subscriptions for the authenticated ISP
    - Supports pagination (skip, limit)
    - Supports filtering by status, customer_id, router_id
    - Requires valid JWT access token
    """
    try:
        customer_uuid = UUID(customer_id) if customer_id else None
        router_uuid = UUID(router_id) if router_id else None

        subscriptions, total = subscription_service.get_subscriptions(
            db=db,
            isp_id=current_isp.id,
            skip=skip,
            limit=limit,
            status_filter=status,
            customer_id=customer_uuid,
            router_id=router_uuid
        )

        subscription_responses = [
            SubscriptionResponse(
                id=str(s.id),
                isp_id=str(s.isp_id),
                customer_id=str(s.customer_id),
                router_id=str(s.router_id),
                package_id=str(s.package_id),
                package_type=s.package_type,
                username=s.username,
                password=s.password,  # Note: In production, consider masking this
                ip_address=s.ip_address,
                status=s.status,
                start_at=s.start_at.isoformat() if s.start_at else None,
                end_at=s.end_at.isoformat() if s.end_at else None,
                created_at=s.created_at.isoformat(),
                updated_at=s.updated_at.isoformat()
            )
            for s in subscriptions
        ]

        return subscription_responses
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer_id or router_id format"
        )
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve subscriptions: {str(e)}"
        )


@router.get(
    "/{subscription_id}",
    response_model=SubscriptionResponse,
    summary="Get Subscription",
    description="Get subscription details by ID."
)
def get_subscription(
    subscription_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Get subscription details.

    This endpoint:
    - Returns subscription details by ID
    - Only accessible by subscription owner (ISP)
    - Requires valid JWT access token
    """
    try:
        subscription_uuid = UUID(subscription_id)
        subscription = subscription_service.get_subscription_by_id(
            db=db,
            subscription_id=subscription_uuid,
            isp_id=current_isp.id
        )

        return SubscriptionResponse(
            id=str(subscription.id),
            isp_id=str(subscription.isp_id),
            customer_id=str(subscription.customer_id),
            router_id=str(subscription.router_id),
            package_id=str(subscription.package_id),
            package_type=subscription.package_type,
            username=subscription.username,
            password=subscription.password,  # Note: In production, consider masking this
            ip_address=subscription.ip_address,
            status=subscription.status,
            start_at=subscription.start_at.isoformat() if subscription.start_at else None,
            end_at=subscription.end_at.isoformat() if subscription.end_at else None,
            created_at=subscription.created_at.isoformat(),
            updated_at=subscription.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve subscription: {str(e)}"
        )


@router.post(
    "/{subscription_id}/activate",
    response_model=SubscriptionActionResponse,
    summary="Activate Subscription",
    description="Activate subscription on MikroTik router. Creates user/queue and sets dates."
)
def activate_subscription(
    subscription_id: str,
    request: SubscriptionActionRequest = SubscriptionActionRequest(),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Activate subscription on MikroTik router.

    This endpoint:
    - Creates PPPoE secret or Static queue on router
    - Sets start_at and end_at dates
    - Changes status to 'active'
    - Only works for 'pending' subscriptions
    - Requires valid JWT access token
    """
    try:
        subscription_uuid = UUID(subscription_id)
        subscription = subscription_service.activate_subscription(
            db=db,
            subscription_id=subscription_uuid,
            isp_id=current_isp.id,
            api_password=request.api_password
        )

        return SubscriptionActionResponse(
            status_code=status.HTTP_200_OK,
            message="Subscription activated successfully",
            subscription_id=str(subscription.id),
            status=subscription.status
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate subscription: {str(e)}"
        )


@router.post(
    "/{subscription_id}/suspend",
    response_model=SubscriptionActionResponse,
    summary="Suspend Subscription",
    description="Suspend subscription (disable on MikroTik router)."
)
def suspend_subscription(
    subscription_id: str,
    request: SubscriptionActionRequest = SubscriptionActionRequest(),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Suspend subscription.

    This endpoint:
    - Disables PPPoE secret or Static queue on router
    - Changes status to 'suspended'
    - Only works for 'active' subscriptions
    - Requires valid JWT access token
    """
    try:
        subscription_uuid = UUID(subscription_id)
        subscription = subscription_service.suspend_subscription(
            db=db,
            subscription_id=subscription_uuid,
            isp_id=current_isp.id,
            api_password=request.api_password
        )

        return SubscriptionActionResponse(
            status_code=status.HTTP_200_OK,
            message="Subscription suspended successfully",
            subscription_id=str(subscription.id),
            status=subscription.status
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to suspend subscription: {str(e)}"
        )


@router.post(
    "/{subscription_id}/resume",
    response_model=SubscriptionActionResponse,
    summary="Resume Subscription",
    description="Resume suspended subscription (re-enable on MikroTik router)."
)
def resume_subscription(
    subscription_id: str,
    request: SubscriptionActionRequest = SubscriptionActionRequest(),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Resume subscription.

    This endpoint:
    - Re-enables PPPoE secret or Static queue on router
    - Changes status to 'active'
    - Only works for 'suspended' subscriptions
    - Requires valid JWT access token
    """
    try:
        subscription_uuid = UUID(subscription_id)
        subscription = subscription_service.resume_subscription(
            db=db,
            subscription_id=subscription_uuid,
            isp_id=current_isp.id,
            api_password=request.api_password
        )

        return SubscriptionActionResponse(
            status_code=status.HTTP_200_OK,
            message="Subscription resumed successfully",
            subscription_id=str(subscription.id),
            status=subscription.status
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume subscription: {str(e)}"
        )


@router.post(
    "/{subscription_id}/terminate",
    response_model=SubscriptionActionResponse,
    summary="Terminate Subscription",
    description="Terminate subscription (remove from MikroTik router)."
)
def terminate_subscription(
    subscription_id: str,
    request: SubscriptionActionRequest = SubscriptionActionRequest(),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Terminate subscription.

    This endpoint:
    - Removes PPPoE secret or Static queue from router
    - Changes status to 'terminated'
    - Works for any status except 'terminated'
    - Requires valid JWT access token
    """
    try:
        subscription_uuid = UUID(subscription_id)
        subscription = subscription_service.terminate_subscription(
            db=db,
            subscription_id=subscription_uuid,
            isp_id=current_isp.id,
            api_password=request.api_password
        )

        return SubscriptionActionResponse(
            status_code=status.HTTP_200_OK,
            message="Subscription terminated successfully",
            subscription_id=str(subscription.id),
            status=subscription.status
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid subscription ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to terminate subscription: {str(e)}"
        )

