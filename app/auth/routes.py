"""Authentication API routes."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from app.auth.schemas import (
    EmailVerifyResponse,
    ISPLoginRequest,
    ISPLoginResponse,
    ISPLoginOTPRequest,
    ISPLoginOTPResponse,
    ISPRegisterRequest,
    ISPRegisterResponse,
    RefreshTokenRequest,
    RefreshTokenResponse,
    LogoutRequest,
    LogoutResponse,
)
from app.auth.dependencies import get_current_isp
from app.auth.services import auth_service
from app.database import get_db
from app.isps.models import ISPDetails

router = APIRouter(prefix="/api/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=ISPRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new ISP",
    description="Register a new ISP account. A verification email will be sent to the provided email address."
)
async def register(
    request: ISPRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new ISP.

    This endpoint:
    - Creates a new ISP account with is_verified=False and is_active=False
    - Hashes the password using bcrypt
    - Generates a secure verification token
    - Stores the token with a 30-minute expiry
    - Sends a verification email via Brevo API
    """
    try:
        isp_id = await auth_service.register_isp(
            db=db,
            name=request.name,
            email=request.email,
            password=request.password
        )
        return ISPRegisterResponse(
            status_code=status.HTTP_201_CREATED,
            message="Registration successful. Please check your email to verify your account.",
            isp_id=str(isp_id)
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Registration failed: {str(e)}"
        )


@router.get(
    "/verify-email",
    response_model=EmailVerifyResponse,
    summary="Verify email address",
    description="Verify ISP email address using the token sent via email."
)
def verify_email(
    token: str = Query(..., description="Verification token from email"),
    db: Session = Depends(get_db)
):
    """
    Verify email address using token.

    This endpoint:
    - Validates the verification token
    - Ensures token is not expired (30 minutes)
    - Ensures token has not been used before
    - Marks ISP as verified (is_verified=True)
    - Marks ISP as active (is_active=True)
    - Sets used_at timestamp on the token
    """
    try:
        auth_service.verify_email(db=db, token=token)
        return EmailVerifyResponse(
            status_code=status.HTTP_200_OK,
            message="Email verified successfully. Your account is now active."
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Email verification failed: {str(e)}"
        )


@router.post(
    "/login",
    response_model=ISPLoginResponse,
    summary="Login ISP (Step 1: Email + Password)",
    description="Validate ISP credentials and send OTP to email. This is the first step of the login process."
)
async def login(
    request: ISPLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login ISP - Step 1: Validate credentials and send OTP.

    This endpoint:
    - Validates email and password
    - Rejects if email not verified
    - Rejects if account not active
    - Generates a 6-digit OTP
    - Sends OTP to email via Brevo API
    - Returns session_id for OTP verification
    """
    try:
        session_id, isp_id = await auth_service.initiate_login(
            db=db,
            email=request.email,
            password=request.password
        )
        return ISPLoginResponse(
            status_code=status.HTTP_200_OK,
            message="OTP sent to your email. Please check and enter the OTP to complete login.",
            session_id=session_id
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Login failed: {str(e)}"
        )


@router.post(
    "/verify-otp",
    response_model=ISPLoginOTPResponse,
    summary="Verify Login OTP (Step 2: OTP Verification)",
    description="Verify OTP and complete login. Returns JWT access token on success."
)
def verify_login_otp(
    request: ISPLoginOTPRequest,
    http_request: Request,
    db: Session = Depends(get_db)
):
    """
    Login ISP - Step 2: Verify OTP and get JWT token.

    This endpoint:
    - Validates session_id and OTP code
    - Ensures OTP is not expired (10 minutes)
    - Ensures OTP has not been used
    - Tracks OTP attempts (max 3 attempts)
    - Generates and returns JWT access token on success
    """
    try:
        # Extract IP address and user agent from request
        ip_address = http_request.client.host if http_request else None
        user_agent = http_request.headers.get("user-agent") if http_request else None
        
        isp, access_token, refresh_token = auth_service.verify_login_otp(
            db=db,
            session_id=request.session_id,
            otp=request.otp,
            ip_address=ip_address,
            user_agent=user_agent
        )
        return ISPLoginOTPResponse(
            status_code=status.HTTP_200_OK,
            message="Login successful",
            access_token=access_token,
            refresh_token=refresh_token,
            token_type="bearer"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"OTP verification failed: {str(e)}"
        )


@router.post(
    "/refresh-token",
    response_model=RefreshTokenResponse,
    summary="Refresh Access Token",
    description="Generate a new access token using a valid refresh token."
)
def refresh_token(
    request: RefreshTokenRequest,
    db: Session = Depends(get_db)
):
    """
    Refresh access token using refresh token.

    This endpoint:
    - Validates the refresh token
    - Checks if refresh token is not revoked
    - Checks if refresh token is not expired
    - Verifies ISP account is still active
    - Generates and returns a new access token
    """
    try:
        isp, new_access_token = auth_service.refresh_access_token(
            db=db,
            refresh_token_str=request.refresh_token
        )
        return RefreshTokenResponse(
            status_code=status.HTTP_200_OK,
            message="Access token refreshed successfully",
            access_token=new_access_token,
            token_type="bearer"
        )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Token refresh failed: {str(e)}"
        )


@router.post(
    "/logout",
    response_model=LogoutResponse,
    summary="Logout",
    description="Logout by revoking refresh token(s). Can revoke a specific token or all tokens for the user."
)
def logout(
    request: LogoutRequest,
    current_isp: ISPDetails = Depends(get_current_isp),
    db: Session = Depends(get_db)
):
    """
    Logout ISP by revoking refresh token(s).

    This endpoint:
    - Requires valid JWT access token (authenticated user)
    - If logout_all=True, revokes all refresh tokens for the user (logout from all devices)
    - If refresh_token is provided, revokes only that specific token
    - If neither is provided, revokes all tokens (default behavior)
    """
    try:
        if request.logout_all or not request.refresh_token:
            # Revoke all refresh tokens for this ISP
            revoked_count = auth_service.revoke_all_refresh_tokens(
                db=db,
                isp_id=current_isp.id
            )
            return LogoutResponse(
                status_code=status.HTTP_200_OK,
                message=f"Logged out successfully. {revoked_count} token(s) revoked."
            )
        else:
            # Revoke specific refresh token
            revoked = auth_service.revoke_refresh_token(
                db=db,
                refresh_token_str=request.refresh_token,
                isp_id=current_isp.id
            )
            if revoked:
                return LogoutResponse(
                    status_code=status.HTTP_200_OK,
                    message="Logged out successfully. Refresh token revoked."
                )
            else:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail="Refresh token not found or already revoked"
                )
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Logout failed: {str(e)}"
        )

