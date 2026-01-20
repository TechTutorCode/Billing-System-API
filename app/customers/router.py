"""Customer API routes."""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_isp
from app.database import get_db
from app.isps.models import ISPDetails
from app.customers.schemas import ChangePasswordRequest, CustomerCreate, CustomerResponse, CustomerUpdate
from app.customers.service import customer_service

router = APIRouter(prefix="/customers", tags=["Customers"])


@router.post(
    "",
    response_model=CustomerResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create Customer",
    description="Create a new customer for the authenticated ISP."
)
def create_customer(
    request: CustomerCreate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Create a new customer.

    This endpoint:
    - Creates a customer record in the database
    - Requires at least one contact method (email or phone)
    - Requires valid JWT access token
    - Sets customer status to 'active' by default
    """
    try:
        customer = customer_service.create_customer(
            db=db,
            isp_id=current_isp.id,
            customer_data=request.model_dump(exclude_none=True)
        )

        return CustomerResponse(
            id=str(customer.id),
            isp_id=str(customer.isp_id),
            account_number=customer.account_number,
            first_name=customer.first_name,
            last_name=customer.last_name,
            email=customer.email,
            phone=customer.phone,
            id_number=customer.id_number,
            address=customer.address,
            status=customer.status,
            created_at=customer.created_at.isoformat(),
            updated_at=customer.updated_at.isoformat()
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to create customer: {str(e)}"
        )


@router.get(
    "",
    response_model=List[CustomerResponse],
    summary="List Customers",
    description="Get list of customers with pagination and filters."
)
def list_customers(
    skip: int = Query(default=0, ge=0, description="Number of records to skip"),
    limit: int = Query(default=100, ge=1, le=1000, description="Maximum number of records to return"),
    status: Optional[str] = Query(default=None, description="Filter by status (active, suspended, terminated)"),
    search: Optional[str] = Query(default=None, description="Search in name, email, or phone"),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    List customers with pagination and filters.

    This endpoint:
    - Returns customers for the authenticated ISP
    - Supports pagination (skip, limit)
    - Supports filtering by status
    - Supports searching by name, email, or phone
    - Requires valid JWT access token
    """
    try:
        customers, total = customer_service.get_customers(
            db=db,
            isp_id=current_isp.id,
            skip=skip,
            limit=limit,
            status_filter=status,
            search=search
        )

        customer_responses = [
            CustomerResponse(
                id=str(c.id),
                isp_id=str(c.isp_id),
                account_number=c.account_number,
                first_name=c.first_name,
                last_name=c.last_name,
                email=c.email,
                phone=c.phone,
                id_number=c.id_number,
                address=c.address,
                status=c.status,
                created_at=c.created_at.isoformat(),
                updated_at=c.updated_at.isoformat()
            )
            for c in customers
        ]

        return customer_responses
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customers: {str(e)}"
        )


@router.get(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Get Customer",
    description="Get customer details by ID."
)
def get_customer(
    customer_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Get customer details.

    This endpoint:
    - Returns customer details by ID
    - Only accessible by customer owner (ISP)
    - Requires valid JWT access token
    """
    try:
        customer_uuid = UUID(customer_id)
        customer = customer_service.get_customer_by_id(
            db=db,
            customer_id=customer_uuid,
            isp_id=current_isp.id
        )

        return CustomerResponse(
            id=str(customer.id),
            isp_id=str(customer.isp_id),
            account_number=customer.account_number,
            first_name=customer.first_name,
            last_name=customer.last_name,
            email=customer.email,
            phone=customer.phone,
            id_number=customer.id_number,
            address=customer.address,
            status=customer.status,
            created_at=customer.created_at.isoformat(),
            updated_at=customer.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve customer: {str(e)}"
        )


@router.put(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Update Customer",
    description="Update customer information."
)
def update_customer(
    customer_id: str,
    request: CustomerUpdate,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Update customer information.

    This endpoint:
    - Updates customer fields (only provided fields)
    - Validates status transitions
    - Ensures at least one contact method remains
    - Only accessible by customer owner (ISP)
    - Requires valid JWT access token
    """
    try:
        customer_uuid = UUID(customer_id)
        customer = customer_service.update_customer(
            db=db,
            customer_id=customer_uuid,
            isp_id=current_isp.id,
            customer_data=request.model_dump(exclude_none=True)
        )

        return CustomerResponse(
            id=str(customer.id),
            isp_id=str(customer.isp_id),
            account_number=customer.account_number,
            first_name=customer.first_name,
            last_name=customer.last_name,
            email=customer.email,
            phone=customer.phone,
            id_number=customer.id_number,
            address=customer.address,
            status=customer.status,
            created_at=customer.created_at.isoformat(),
            updated_at=customer.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update customer: {str(e)}"
        )


@router.delete(
    "/{customer_id}",
    response_model=CustomerResponse,
    summary="Delete Customer",
    description="Soft delete customer (set status to terminated)."
)
def delete_customer(
    customer_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Delete customer (soft delete).

    This endpoint:
    - Sets customer status to 'terminated' (soft delete)
    - Cannot delete customer with active subscriptions (TODO: implement check)
    - Only accessible by customer owner (ISP)
    - Requires valid JWT access token
    """
    try:
        customer_uuid = UUID(customer_id)
        customer = customer_service.delete_customer(
            db=db,
            customer_id=customer_uuid,
            isp_id=current_isp.id
        )

        return CustomerResponse(
            id=str(customer.id),
            isp_id=str(customer.isp_id),
            account_number=customer.account_number,
            first_name=customer.first_name,
            last_name=customer.last_name,
            email=customer.email,
            phone=customer.phone,
            id_number=customer.id_number,
            address=customer.address,
            status=customer.status,
            created_at=customer.created_at.isoformat(),
            updated_at=customer.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete customer: {str(e)}"
        )


@router.post(
    "/{customer_id}/activate",
    response_model=CustomerResponse,
    status_code=status.HTTP_200_OK,
    summary="Activate Customer",
    description="Activate a terminated customer (set status to active)."
)
def activate_customer(
    customer_id: str,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Activate a terminated customer.

    This endpoint:
    - Sets customer status to 'active'
    - Only works for terminated customers
    - Only accessible by customer owner (ISP)
    - Requires valid JWT access token
    """
    try:
        customer_uuid = UUID(customer_id)
        customer = customer_service.activate_customer(
            db=db,
            customer_id=customer_uuid,
            isp_id=current_isp.id
        )

        return CustomerResponse(
            id=str(customer.id),
            isp_id=str(customer.isp_id),
            account_number=customer.account_number,
            first_name=customer.first_name,
            last_name=customer.last_name,
            email=customer.email,
            phone=customer.phone,
            id_number=customer.id_number,
            address=customer.address,
            status=customer.status,
            created_at=customer.created_at.isoformat(),
            updated_at=customer.updated_at.isoformat()
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to activate customer: {str(e)}"
        )


@router.post(
    "/{customer_id}/change-password",
    status_code=status.HTTP_200_OK,
    summary="Change Customer Password",
    description="Change customer password. Requires current password verification."
)
def change_customer_password(
    customer_id: str,
    request: ChangePasswordRequest,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Change customer password.

    This endpoint:
    - Verifies the current password
    - Updates to the new password
    - Only accessible by customer owner (ISP)
    - Requires valid JWT access token
    """
    try:
        customer_uuid = UUID(customer_id)
        customer = customer_service.change_customer_password(
            db=db,
            customer_id=customer_uuid,
            isp_id=current_isp.id,
            current_password=request.current_password,
            new_password=request.new_password
        )

        return {
            "status_code": status.HTTP_200_OK,
            "message": "Password changed successfully",
            "customer_id": str(customer.id),
            "account_number": customer.account_number
        }
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid customer ID format"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to change password: {str(e)}"
        )

