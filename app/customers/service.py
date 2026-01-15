"""Customer business logic services."""

import logging
from datetime import datetime, timezone
from typing import List, Optional
from uuid import UUID

from fastapi import HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_

from app.customers.models import Customer, CustomerStatus

logger = logging.getLogger(__name__)


class CustomerService:
    """Service for customer-related operations."""

    @staticmethod
    def generate_account_number(db: Session) -> str:
        """
        Generate a unique account number in format 'cust001', 'cust002', etc.

        Args:
            db: Database session

        Returns:
            Unique account number string
        """
        # Get the highest account number
        last_customer = (
            db.query(Customer)
            .filter(Customer.account_number.like('cust%'))
            .order_by(Customer.account_number.desc())
            .first()
        )

        if last_customer:
            # Extract the number part and increment
            try:
                last_number = int(last_customer.account_number.replace('cust', ''))
                next_number = last_number + 1
            except ValueError:
                # If format is unexpected, start from 1
                next_number = 1
        else:
            # First customer
            next_number = 1

        # Format as cust001, cust002, etc. (3 digits minimum)
        account_number = f"cust{next_number:03d}"

        # Ensure uniqueness (handle race conditions)
        while db.query(Customer).filter(Customer.account_number == account_number).first():
            next_number += 1
            account_number = f"cust{next_number:03d}"

        return account_number

    @staticmethod
    def create_customer(
        db: Session,
        isp_id: UUID,
        customer_data: dict
    ) -> Customer:
        """
        Create a new customer.

        Args:
            db: Database session
            isp_id: ISP ID
            customer_data: Customer data dictionary

        Returns:
            Customer instance

        Raises:
            HTTPException: If validation fails
        """
        # Ensure at least one contact method
        if not customer_data.get("email") and not customer_data.get("phone"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Either email or phone must be provided"
            )

        # Generate unique account number
        account_number = CustomerService.generate_account_number(db)

        # Create customer
        customer = Customer(
            isp_id=isp_id,
            account_number=account_number,
            **customer_data,
            status=CustomerStatus.ACTIVE.value
        )
        db.add(customer)
        db.commit()
        db.refresh(customer)

        logger.info(f"Created customer {customer.id} for ISP {isp_id}")
        return customer

    @staticmethod
    def get_customers(
        db: Session,
        isp_id: UUID,
        skip: int = 0,
        limit: int = 100,
        status_filter: Optional[str] = None,
        search: Optional[str] = None
    ) -> tuple[List[Customer], int]:
        """
        Get customers with pagination and filters.

        Args:
            db: Database session
            isp_id: ISP ID
            skip: Number of records to skip
            limit: Maximum number of records to return
            status_filter: Filter by status (active, suspended, terminated)
            search: Search in name, email, or phone

        Returns:
            Tuple of (list of customers, total count)
        """
        query = db.query(Customer).filter(Customer.isp_id == isp_id)

        # Apply status filter
        if status_filter:
            query = query.filter(Customer.status == status_filter.lower())

        # Apply search filter
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    Customer.account_number.ilike(search_pattern),
                    Customer.first_name.ilike(search_pattern),
                    Customer.last_name.ilike(search_pattern),
                    Customer.email.ilike(search_pattern),
                    Customer.phone.ilike(search_pattern)
                )
            )

        # Get total count
        total = query.count()

        # Apply pagination
        customers = query.order_by(Customer.created_at.desc()).offset(skip).limit(limit).all()

        return customers, total

    @staticmethod
    def get_customer_by_id(
        db: Session,
        customer_id: UUID,
        isp_id: UUID
    ) -> Customer:
        """
        Get customer by ID.

        Args:
            db: Database session
            customer_id: Customer ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            Customer instance

        Raises:
            HTTPException: If customer not found or doesn't belong to ISP
        """
        customer = (
            db.query(Customer)
            .filter(
                Customer.id == customer_id,
                Customer.isp_id == isp_id
            )
            .first()
        )

        if not customer:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Customer not found or does not belong to you"
            )

        return customer

    @staticmethod
    def update_customer(
        db: Session,
        customer_id: UUID,
        isp_id: UUID,
        customer_data: dict
    ) -> Customer:
        """
        Update a customer.

        Args:
            db: Database session
            customer_id: Customer ID
            isp_id: ISP ID (for ownership verification)
            customer_data: Customer data dictionary (only provided fields)

        Returns:
            Updated Customer instance

        Raises:
            HTTPException: If customer not found or validation fails
        """
        customer = CustomerService.get_customer_by_id(db, customer_id, isp_id)

        # Validate status transition
        if "status" in customer_data and customer_data["status"]:
            new_status = customer_data["status"].lower()
            current_status = customer.status

            # Validate status transition rules
            if current_status == CustomerStatus.TERMINATED.value:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Cannot change status of terminated customer"
                )

            if new_status not in [s.value for s in CustomerStatus]:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid status: {new_status}"
                )

            customer_data["status"] = new_status

        # Ensure at least one contact method after update
        email = customer_data.get("email", customer.email)
        phone = customer_data.get("phone", customer.phone)
        if email is None and phone is None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer must have at least one contact method (email or phone)"
            )

        # Update fields
        for key, value in customer_data.items():
            if value is not None:
                setattr(customer, key, value)

        customer.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(customer)

        logger.info(f"Updated customer {customer_id}")
        return customer

    @staticmethod
    def delete_customer(
        db: Session,
        customer_id: UUID,
        isp_id: UUID
    ) -> Customer:
        """
        Soft delete a customer (set status to terminated).

        Args:
            db: Database session
            customer_id: Customer ID
            isp_id: ISP ID (for ownership verification)

        Returns:
            Updated Customer instance

        Raises:
            HTTPException: If customer not found or has active subscriptions
        """
        customer = CustomerService.get_customer_by_id(db, customer_id, isp_id)

        # Check if customer has active subscriptions
        # TODO: Implement subscription check when subscriptions module is created
        # For now, we'll just check if customer is already terminated
        if customer.status == CustomerStatus.TERMINATED.value:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer is already terminated"
            )

        # Soft delete: set status to terminated
        customer.status = CustomerStatus.TERMINATED.value
        customer.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(customer)

        logger.info(f"Terminated customer {customer_id}")
        return customer


# Global instance
customer_service = CustomerService()

