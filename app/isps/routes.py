"""ISP profile API routes."""

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, status
from sqlalchemy.orm import Session

from app.auth.dependencies import get_current_isp
from app.cloudinary.service import cloudinary_service
from app.database import get_db
from app.isps.models import ISPDetails
from app.isps.schemas import (
    ISPProfileCompleteRequest,
    ISPProfileCompleteResponse,
    ISPProfileResponse,
    ISPProfileUpdateRequest,
    ISPProfileUpdateResponse,
)
from app.isps.services import isp_service

router = APIRouter(prefix="/isps", tags=["ISP Profile"])


@router.get(
    "/profile",
    response_model=ISPProfileResponse,
    summary="Get ISP Profile",
    description="Get the authenticated ISP's profile information."
)
def get_profile(
    current_isp: ISPDetails = Depends(get_current_isp)
):
    """
    Get ISP profile.

    This endpoint:
    - Returns the authenticated ISP's profile information
    - Requires valid JWT access token
    """
    try:
        profile = isp_service.get_isp_profile(current_isp)
        return profile
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve profile: {str(e)}"
        )


@router.post(
    "/profile/complete",
    response_model=ISPProfileCompleteResponse,
    summary="Complete ISP Profile",
    description="Complete ISP profile with additional information. Logo can be uploaded as a file. Name is already set during registration."
)
async def complete_profile(
    phone: str = Form(None, max_length=50, description="Phone number"),
    location: str = Form(None, max_length=255, description="Location"),
    website: str = Form(None, max_length=255, description="Website URL"),
    logo: UploadFile = File(None, description="ISP logo image file"),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Complete ISP profile.

    This endpoint:
    - Completes the ISP profile with additional information
    - Uploads logo image to Cloudinary if provided
    - Requires valid JWT access token
    - Can only be used if profile is not already completed
    """
    try:
        logo_url = None
        
        # Upload logo to Cloudinary if provided
        if logo:
            # Validate file type
            if not logo.content_type or not logo.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Logo must be an image file"
                )
            
            # Read file content
            file_content = await logo.read()
            
            # Upload to Cloudinary with ISP ID as part of public_id
            public_id = f"isp_{current_isp.id}_logo"
            logo_url = cloudinary_service.upload_image(
                file_content=file_content,
                folder="isp_logos",
                public_id=public_id
            )
        
        # Create profile data object
        profile_data = ISPProfileCompleteRequest(
            phone=phone if phone else None,
            location=location if location else None,
            website=website if website else None
        )
        
        profile = isp_service.complete_isp_profile(
            db=db,
            isp=current_isp,
            profile_data=profile_data,
            logo_url=logo_url
        )
        
        return ISPProfileCompleteResponse(
            status_code=status.HTTP_200_OK,
            message="Profile completed successfully",
            profile=profile
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to complete profile: {str(e)}"
        )


@router.put(
    "/profile",
    response_model=ISPProfileUpdateResponse,
    summary="Update ISP Profile",
    description="Update ISP profile information. Only provided fields will be updated. Logo can be uploaded as a file."
)
async def update_profile(
    name: str = Form(None, min_length=1, max_length=255, description="ISP name"),
    phone: str = Form(None, max_length=50, description="Phone number"),
    location: str = Form(None, max_length=255, description="Location"),
    website: str = Form(None, max_length=255, description="Website URL"),
    logo: UploadFile = File(None, description="ISP logo image file"),
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Update ISP profile.

    This endpoint:
    - Updates the ISP profile with provided information
    - Uploads logo image to Cloudinary if provided
    - Requires valid JWT access token
    - Only updates fields that are provided (partial update)
    """
    try:
        logo_url = None
        
        # Upload logo to Cloudinary if provided
        if logo:
            # Validate file type
            if not logo.content_type or not logo.content_type.startswith("image/"):
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Logo must be an image file"
                )
            
            # Read file content
            file_content = await logo.read()
            
            # Upload to Cloudinary with ISP ID as part of public_id
            public_id = f"isp_{current_isp.id}_logo"
            logo_url = cloudinary_service.upload_image(
                file_content=file_content,
                folder="isp_logos",
                public_id=public_id
            )
        
        # Create profile data object
        profile_data = ISPProfileUpdateRequest(
            name=name if name else None,
            phone=phone if phone else None,
            location=location if location else None,
            website=website if website else None
        )
        
        profile = isp_service.update_isp_profile(
            db=db,
            isp=current_isp,
            profile_data=profile_data,
            logo_url=logo_url
        )
        
        return ISPProfileUpdateResponse(
            status_code=status.HTTP_200_OK,
            message="Profile updated successfully",
            profile=profile
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to update profile: {str(e)}"
        )

