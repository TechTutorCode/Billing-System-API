"""Cloudinary service for image uploads."""

import cloudinary
import cloudinary.uploader
from fastapi import HTTPException, status

from app.config import get_settings

settings = get_settings()

# Configure Cloudinary
cloudinary.config(
    cloud_name=settings.CLOUDINARY_CLOUD_NAME,
    api_key=settings.CLOUDINARY_API_KEY,
    api_secret=settings.CLOUDINARY_API_SECRET
)


class CloudinaryService:
    """Service for Cloudinary image uploads."""

    @staticmethod
    def upload_image(file_content: bytes, folder: str = "isp_logos", public_id: str = None) -> str:
        """
        Upload image to Cloudinary.

        Args:
            file_content: Image file content as bytes
            folder: Cloudinary folder path
            public_id: Optional public ID for the image

        Returns:
            URL of the uploaded image

        Raises:
            HTTPException: If upload fails
        """
        try:
            # Upload image to Cloudinary
            upload_result = cloudinary.uploader.upload(
                file_content,
                folder=folder,
                public_id=public_id,
                resource_type="image",
                overwrite=True,
                invalidate=True
            )

            # Extract secure URL from response
            image_url = upload_result.get("secure_url") or upload_result.get("url")
            
            if not image_url:
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to get image URL from Cloudinary"
                )

            return image_url

        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=f"Failed to upload image to Cloudinary: {str(e)}"
            )

    @staticmethod
    def delete_image(public_id: str) -> bool:
        """
        Delete image from Cloudinary.

        Args:
            public_id: Public ID of the image to delete

        Returns:
            True if deletion successful
        """
        try:
            result = cloudinary.uploader.destroy(public_id)
            return result.get("result") == "ok"
        except Exception:
            return False


# Global instance
cloudinary_service = CloudinaryService()


