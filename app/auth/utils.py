"""Authentication utility functions."""

import bcrypt
import jwt
from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import UUID

from app.config import get_settings

settings = get_settings()


def hash_password(password: str) -> str:
    """
    Hash a password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Hashed password as string
    """
    salt = bcrypt.gensalt()
    hashed = bcrypt.hashpw(password.encode("utf-8"), salt)
    return hashed.decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """
    Verify a password against a hash.

    Args:
        plain_password: Plain text password to verify
        hashed_password: Hashed password to compare against

    Returns:
        True if password matches, False otherwise
    """
    return bcrypt.checkpw(
        plain_password.encode("utf-8"),
        hashed_password.encode("utf-8")
    )


def generate_jwt_token(isp_id: UUID, email: str, token_type: str = "access") -> str:
    """
    Generate a JWT token (access or refresh).

    Args:
        isp_id: ISP UUID
        email: ISP email address
        token_type: Type of token ("access" or "refresh")

    Returns:
        JWT token string
    """
    if token_type == "access":
        if not settings.JWT_SECRET_KEY:
            raise ValueError("JWT_SECRET_KEY not configured")
        secret_key = settings.JWT_SECRET_KEY
        expire = datetime.now(timezone.utc) + timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)
    else:  # refresh
        if not settings.JWT_REFRESH_SECRET_KEY:
            raise ValueError("JWT_REFRESH_SECRET_KEY not configured")
        secret_key = settings.JWT_REFRESH_SECRET_KEY
        expire = datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS)
    
    payload = {
        "sub": str(isp_id),  # Subject (ISP ID)
        "email": email,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "type": token_type
    }
    
    token = jwt.encode(
        payload,
        secret_key,
        algorithm=settings.JWT_ALGORITHM
    )
    
    # PyJWT 2.x returns string, but handle both cases
    if isinstance(token, bytes):
        return token.decode("utf-8")
    return token


def verify_jwt_token(token: str, token_type: str = "access") -> Optional[dict]:
    """
    Verify and decode a JWT token.

    Args:
        token: JWT token string
        token_type: Type of token ("access" or "refresh")

    Returns:
        Decoded token payload if valid, None otherwise
    """
    try:
        if token_type == "access":
            if not settings.JWT_SECRET_KEY:
                return None
            secret_key = settings.JWT_SECRET_KEY
        else:  # refresh
            if not settings.JWT_REFRESH_SECRET_KEY:
                return None
            secret_key = settings.JWT_REFRESH_SECRET_KEY
            
        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[settings.JWT_ALGORITHM]
        )
        
        # Verify token type matches
        if payload.get("type") != token_type:
            return None
            
        return payload
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

