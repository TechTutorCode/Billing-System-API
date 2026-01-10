"""Authentication dependencies for protected routes."""

from typing import Optional
from uuid import UUID

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.auth.utils import verify_jwt_token
from app.database import get_db
from app.isps.models import ISPDetails

security = HTTPBearer()


def get_current_isp(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> ISPDetails:
    """
    Dependency to get current authenticated ISP from JWT token.

    Args:
        credentials: HTTP Bearer token credentials
        db: Database session

    Returns:
        ISPDetails instance

    Raises:
        HTTPException: If token is invalid or ISP not found
    """
    token = credentials.credentials
    
    # Verify JWT token
    payload = verify_jwt_token(token, token_type="access")
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token"
        )
    
    # Extract ISP ID from token
    isp_id_str = payload.get("sub")
    if not isp_id_str:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    try:
        isp_id = UUID(isp_id_str)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token"
        )
    
    # Get ISP from database
    isp = db.query(ISPDetails).filter(ISPDetails.id == isp_id).first()
    if not isp:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="ISP not found"
        )
    
    # Check if ISP is active
    if not isp.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is not active"
        )
    
    return isp


