"""ISP profile business logic services."""

from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.isps.models import ISPDetails
from app.isps.schemas import (
    ISPProfileCompleteRequest,
    ISPProfileResponse,
    ISPProfileUpdateRequest,
)


class ISPService:
    """Service for ISP profile operations."""

    @staticmethod
    def get_isp_profile(isp: ISPDetails) -> ISPProfileResponse:
        """
        Get ISP profile.

        Args:
            isp: ISPDetails instance

        Returns:
            ISPProfileResponse
        """
        return ISPProfileResponse(
            id=str(isp.id),
            name=isp.name,
            email=isp.email,
            phone=isp.phone,
            location=isp.location,
            logo_url=isp.logo_url,
            website=isp.website,
            is_verified=isp.is_verified,
            is_active=isp.is_active,
            created_at=isp.created_at.isoformat() if isp.created_at else ""
        )

    @staticmethod
    def complete_isp_profile(
        db: Session,
        isp: ISPDetails,
        profile_data: ISPProfileCompleteRequest,
        logo_url: Optional[str] = None
    ) -> ISPProfileResponse:
        """
        Complete ISP profile with additional information.

        Args:
            db: Database session
            isp: ISPDetails instance
            profile_data: Profile completion data
            logo_url: Optional logo URL from Cloudinary

        Returns:
            ISPProfileResponse

        Raises:
            HTTPException: If profile is already completed
        """
        # Check if profile is already completed (has phone and location)
        # Name is set during registration, so we check for other required fields
        if isp.phone and isp.location:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Profile is already completed"
            )

        # Update ISP profile
        # Name is not updated here as it's already set during registration
        isp.phone = profile_data.phone
        isp.location = profile_data.location
        if logo_url:
            isp.logo_url = logo_url
        isp.website = profile_data.website

        db.commit()
        db.refresh(isp)

        return ISPService.get_isp_profile(isp)

    @staticmethod
    def update_isp_profile(
        db: Session,
        isp: ISPDetails,
        profile_data: ISPProfileUpdateRequest,
        logo_url: Optional[str] = None
    ) -> ISPProfileResponse:
        """
        Update ISP profile.

        Args:
            db: Database session
            isp: ISPDetails instance
            profile_data: Profile update data
            logo_url: Optional logo URL from Cloudinary

        Returns:
            ISPProfileResponse

        Raises:
            HTTPException: If no fields to update
        """
        # Check if at least one field is provided
        if not any([
            profile_data.name is not None,
            profile_data.phone is not None,
            profile_data.location is not None,
            logo_url is not None,
            profile_data.website is not None
        ]):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="At least one field must be provided for update"
            )

        # Update only provided fields
        if profile_data.name is not None:
            isp.name = profile_data.name
        if profile_data.phone is not None:
            isp.phone = profile_data.phone
        if profile_data.location is not None:
            isp.location = profile_data.location
        if logo_url is not None:
            isp.logo_url = logo_url
        if profile_data.website is not None:
            isp.website = profile_data.website

        db.commit()
        db.refresh(isp)

        return ISPService.get_isp_profile(isp)


# Global instance
isp_service = ISPService()

