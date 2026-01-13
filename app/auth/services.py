"""Authentication business logic services."""

import secrets
import uuid
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.email.service import email_service
from app.email_verification.models import EmailVerification
from app.isps.models import ISPDetails
from app.otp.models import LoginOTP
from app.auth.models import RefreshToken
from app.auth.login_history_models import LoginHistory
from app.auth.utils import hash_password, verify_password, generate_jwt_token, verify_jwt_token


class AuthService:
    """Service for authentication-related operations."""

    @staticmethod
    def generate_verification_token() -> str:
        """
        Generate a secure random token for email verification.

        Returns:
            Random token string
        """
        return secrets.token_urlsafe(32)

    @staticmethod
    async def register_isp(
        db: Session,
        name: str,
        email: str,
        password: str
    ) -> uuid.UUID:
        """
        Register a new ISP and send verification email.

        Args:
            db: Database session
            name: ISP name
            email: ISP email address
            password: Plain text password

        Returns:
            UUID of the created ISP

        Raises:
            HTTPException: If email already exists
        """
        # Check if email already exists
        existing_isp = db.query(ISPDetails).filter(ISPDetails.email == email).first()
        if existing_isp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email already registered"
            )

        # Hash password
        password_hash = hash_password(password)

        # Create ISP record
        isp = ISPDetails(
            name=name,
            email=email,
            password_hash=password_hash,
            is_verified=False,
            is_active=False
        )
        db.add(isp)
        db.flush()  # Flush to get the ID without committing

        # Generate verification token
        token = AuthService.generate_verification_token()
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)

        # Create email verification record
        email_verification = EmailVerification(
            isp_id=isp.id,
            token=token,
            expires_at=expires_at
        )
        db.add(email_verification)

        # Commit transaction
        db.commit()
        db.refresh(isp)

        # Send verification email (async, non-blocking)
        try:
            await email_service.send_verification_email(
                recipient_email=email,
                recipient_name=name,
                verification_token=token
            )
        except Exception as e:
            # Log error but don't fail registration
            # The token is stored and can be resent later
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send verification email: {str(e)}")

        return isp.id

    @staticmethod
    def verify_email(db: Session, token: str) -> bool:
        """
        Verify email using token.

        Args:
            db: Database session
            token: Verification token

        Returns:
            True if verification successful

        Raises:
            HTTPException: If token is invalid, expired, or already used
        """
        # Find verification record
        verification = (
            db.query(EmailVerification)
            .filter(EmailVerification.token == token)
            .first()
        )

        if not verification:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid verification token"
            )

        # Check if token is already used
        if verification.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has already been used"
            )

        # Check if token is expired
        if verification.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Verification token has expired"
            )

        # Get ISP record
        isp = db.query(ISPDetails).filter(ISPDetails.id == verification.isp_id).first()
        if not isp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ISP not found"
            )

        # Update ISP to verified and active
        isp.is_verified = True
        isp.is_active = True

        # Mark token as used
        verification.used_at = datetime.now(timezone.utc)

        db.commit()

        return True

    @staticmethod
    def generate_otp() -> str:
        """
        Generate a 6-digit OTP code.

        Returns:
            6-digit OTP string
        """
        return f"{secrets.randbelow(900000) + 100000:06d}"

    @staticmethod
    async def initiate_login(db: Session, email: str, password: str) -> tuple[str, uuid.UUID]:
        """
        Initiate login process - validate credentials and send OTP.

        Args:
            db: Database session
            email: ISP email address
            password: Plain text password

        Returns:
            Tuple of (session_id, isp_id)

        Raises:
            HTTPException: If credentials are invalid, not verified, or not active
        """
        # Find ISP by email
        isp = db.query(ISPDetails).filter(ISPDetails.email == email).first()

        if not isp:
            # Don't reveal if email exists for security
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Verify password
        if not verify_password(password, isp.password_hash):
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid email or password"
            )

        # Check if verified
        if not isp.is_verified:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Email not verified. Please check your email and verify your account."
            )

        # Check if active
        if not isp.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active. Please contact support."
            )

        # Generate OTP
        otp_code = AuthService.generate_otp()
        session_id = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=10)

        # Invalidate any existing OTPs for this ISP (optional, for security)
        db.query(LoginOTP).filter(
            LoginOTP.isp_id == isp.id,
            LoginOTP.used_at.is_(None),
            LoginOTP.expires_at > datetime.now(timezone.utc)
        ).update({"used_at": datetime.now(timezone.utc)})

        # Create new OTP record
        login_otp = LoginOTP(
            isp_id=isp.id,
            otp_code=otp_code,
            session_id=session_id,
            expires_at=expires_at,
            attempts=0
        )
        db.add(login_otp)
        db.commit()

        # Send OTP email (async, non-blocking)
        try:
            await email_service.send_login_otp_email(
                recipient_email=email,
                recipient_name=isp.name,
                otp_code=otp_code
            )
        except Exception as e:
            # Log error but don't fail login initiation
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"Failed to send login OTP email: {str(e)}")

        return session_id, isp.id

    @staticmethod
    def verify_login_otp(db: Session, session_id: str, otp: str) -> tuple[ISPDetails, str]:
        """
        Verify login OTP and return JWT token.

        Args:
            db: Database session
            session_id: Session ID from login initiation
            otp: 6-digit OTP code

        Returns:
            Tuple of (ISP details, JWT token)

        Raises:
            HTTPException: If OTP is invalid, expired, or max attempts exceeded
        """
        # Find OTP record
        login_otp = (
            db.query(LoginOTP)
            .filter(LoginOTP.session_id == session_id)
            .first()
        )

        if not login_otp:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid session ID"
            )

        # Check if OTP is already used
        if login_otp.used_at is not None:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has already been used. Please request a new login."
            )

        # Check if OTP is expired
        if login_otp.expires_at < datetime.now(timezone.utc):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="OTP has expired. Please request a new login."
            )

        # Check max attempts (3 attempts max)
        if login_otp.attempts >= 3:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Maximum OTP attempts exceeded. Please request a new login."
            )

        # Verify OTP code
        if login_otp.otp_code != otp:
            # Increment attempts
            login_otp.attempts += 1
            db.commit()
            
            remaining_attempts = 3 - login_otp.attempts
            if remaining_attempts > 0:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid OTP. {remaining_attempts} attempt(s) remaining."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail="Maximum OTP attempts exceeded. Please request a new login."
                )

        # Get ISP record
        isp = db.query(ISPDetails).filter(ISPDetails.id == login_otp.isp_id).first()
        if not isp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ISP not found"
            )

        # Mark OTP as used
        login_otp.used_at = datetime.now(timezone.utc)
        
        # Generate JWT tokens
        try:
            access_token = generate_jwt_token(isp_id=isp.id, email=isp.email, token_type="access")
            refresh_token_str = generate_jwt_token(isp_id=isp.id, email=isp.email, token_type="refresh")
            
            # Store refresh token in database
            refresh_token_expires = datetime.now(timezone.utc) + timedelta(days=30)
            refresh_token = RefreshToken(
                isp_id=isp.id,
                token=refresh_token_str,
                expires_at=refresh_token_expires,
                revoked=False
            )
            db.add(refresh_token)
            
            # Record login history
            login_history = LoginHistory(
                isp_id=isp.id,
                ip_address=ip_address,
                user_agent=user_agent
            )
            db.add(login_history)
            
            db.commit()
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token"
            )

        return isp, access_token, refresh_token_str

    @staticmethod
    def refresh_access_token(db: Session, refresh_token_str: str) -> tuple[ISPDetails, str]:
        """
        Refresh access token using refresh token.

        Args:
            db: Database session
            refresh_token_str: Refresh token string

        Returns:
            Tuple of (ISP details, new access token)

        Raises:
            HTTPException: If refresh token is invalid, expired, or revoked
        """
        # Verify refresh token
        payload = verify_jwt_token(refresh_token_str, token_type="refresh")
        if not payload:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid or expired refresh token"
            )

        isp_id_str = payload.get("sub")
        if not isp_id_str:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        try:
            isp_id = uuid.UUID(isp_id_str)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid refresh token"
            )

        # Check if refresh token exists in database and is not revoked
        refresh_token = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == refresh_token_str,
                RefreshToken.isp_id == isp_id,
                RefreshToken.revoked == False
            )
            .first()
        )

        if not refresh_token:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token not found or has been revoked"
            )

        # Check if refresh token is expired
        if refresh_token.expires_at < datetime.now(timezone.utc):
            # Mark as revoked
            refresh_token.revoked = True
            refresh_token.revoked_at = datetime.now(timezone.utc)
            db.commit()
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Refresh token has expired"
            )

        # Get ISP record
        isp = db.query(ISPDetails).filter(ISPDetails.id == isp_id).first()
        if not isp:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="ISP not found"
            )

        # Check if ISP is still active
        if not isp.is_active:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Account is not active. Please contact support."
            )

        # Generate new access token
        try:
            new_access_token = generate_jwt_token(isp_id=isp.id, email=isp.email, token_type="access")
        except ValueError as e:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to generate authentication token"
            )

        return isp, new_access_token

    @staticmethod
    def revoke_refresh_token(db: Session, refresh_token_str: str, isp_id: uuid.UUID) -> bool:
        """
        Revoke a specific refresh token.

        Args:
            db: Database session
            refresh_token_str: Refresh token string to revoke
            isp_id: ISP ID (for security check)

        Returns:
            True if token was revoked, False if not found

        Raises:
            HTTPException: If token doesn't belong to the ISP
        """
        # Find the refresh token
        refresh_token = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token == refresh_token_str,
                RefreshToken.isp_id == isp_id,
                RefreshToken.revoked == False
            )
            .first()
        )

        if not refresh_token:
            return False

        # Revoke the token
        refresh_token.revoked = True
        refresh_token.revoked_at = datetime.now(timezone.utc)
        db.commit()

        return True

    @staticmethod
    def revoke_all_refresh_tokens(db: Session, isp_id: uuid.UUID) -> int:
        """
        Revoke all refresh tokens for an ISP (logout from all devices).

        Args:
            db: Database session
            isp_id: ISP ID

        Returns:
            Number of tokens revoked
        """
        # Find all active refresh tokens for this ISP
        refresh_tokens = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.isp_id == isp_id,
                RefreshToken.revoked == False
            )
            .all()
        )

        revoked_count = 0
        now = datetime.now(timezone.utc)
        for token in refresh_tokens:
            token.revoked = True
            token.revoked_at = now
            revoked_count += 1

        if revoked_count > 0:
            db.commit()

        return revoked_count


# Global instance
auth_service = AuthService()

