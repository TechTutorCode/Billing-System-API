"""Email service using Brevo (Sendinblue) Transactional Email API."""

import logging
from typing import Optional

import httpx

from app.config import get_settings

logger = logging.getLogger(__name__)
settings = get_settings()

# Brevo API endpoint
BREVO_API_URL = "https://api.brevo.com/v3/smtp/email"


class EmailService:
    """Service for sending transactional emails via Brevo API."""

    def __init__(self):
        """Initialize email service with API key from settings."""
        self.api_key = settings.BREVO_API_KEY
        self.sender_email = settings.BREVO_SENDER_EMAIL
        self.sender_name = settings.BREVO_SENDER_NAME
        self.verify_url = settings.FRONTEND_VERIFY_URL

    async def send_verification_email(
        self,
        recipient_email: str,
        recipient_name: str,
        verification_token: str
    ) -> bool:
        """
        Send email verification email to ISP.

        Args:
            recipient_email: Email address of the ISP
            recipient_name: Name of the ISP
            verification_token: Verification token to include in the link

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.api_key:
            logger.error("BREVO_API_KEY not configured")
            return False

        if not self.sender_email:
            logger.error("BREVO_SENDER_EMAIL not configured")
            return False

        verification_link = f"{self.verify_url}?token={verification_token}"

        # HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Verify Your Email</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f4f4f4; padding: 20px; border-radius: 5px;">
                <h2 style="color: #2c3e50;">Verify Your Email Address</h2>
                <p>Hello {recipient_name},</p>
                <p>Thank you for registering with our billing system. Please verify your email address by clicking the button below:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <a href="{verification_link}" style="background-color: #3498db; color: white; padding: 12px 30px; text-decoration: none; border-radius: 5px; display: inline-block; font-weight: bold;">Verify Email</a>
                </div>
                <p>Or copy and paste this link into your browser:</p>
                <p style="word-break: break-all; color: #3498db;">{verification_link}</p>
                <p style="color: #7f8c8d; font-size: 12px; margin-top: 30px;">
                    <strong>Note:</strong> This link will expire in 30 minutes. If you didn't create an account, please ignore this email.
                </p>
            </div>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""
        Hello {recipient_name},

        Thank you for registering with our billing system. Please verify your email address by visiting the following link:

        {verification_link}

        This link will expire in 30 minutes. If you didn't create an account, please ignore this email.
        """

        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [
                {
                    "email": recipient_email,
                    "name": recipient_name
                }
            ],
            "subject": "Verify Your Email Address",
            "htmlContent": html_content,
            "textContent": text_content
        }

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    BREVO_API_URL,
                    json=payload,
                    headers=headers
                )

                if response.status_code == 201:
                    logger.info(
                        f"Verification email sent successfully to {recipient_email}"
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to send verification email. "
                        f"Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Timeout while sending verification email via Brevo API")
            return False
        except httpx.RequestError as e:
            logger.error(f"Request error while sending verification email: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while sending verification email: {str(e)}")
            return False


    async def send_login_otp_email(
        self,
        recipient_email: str,
        recipient_name: str,
        otp_code: str
    ) -> bool:
        """
        Send login OTP email to ISP.

        Args:
            recipient_email: Email address of the ISP
            recipient_name: Name of the ISP
            otp_code: 6-digit OTP code

        Returns:
            True if email sent successfully, False otherwise
        """
        if not self.api_key:
            logger.error("BREVO_API_KEY not configured")
            return False

        if not self.sender_email:
            logger.error("BREVO_SENDER_EMAIL not configured")
            return False

        # HTML email template
        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <meta charset="utf-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Your Login OTP</title>
        </head>
        <body style="font-family: Arial, sans-serif; line-height: 1.6; color: #333; max-width: 600px; margin: 0 auto; padding: 20px;">
            <div style="background-color: #f4f4f4; padding: 20px; border-radius: 5px;">
                <h2 style="color: #2c3e50;">Your Login OTP</h2>
                <p>Hello {recipient_name},</p>
                <p>You have requested to login to your account. Use the OTP code below to complete your login:</p>
                <div style="text-align: center; margin: 30px 0;">
                    <div style="background-color: #3498db; color: white; padding: 20px; border-radius: 5px; display: inline-block; font-size: 32px; font-weight: bold; letter-spacing: 5px;">
                        {otp_code}
                    </div>
                </div>
                <p style="color: #7f8c8d; font-size: 12px; margin-top: 30px;">
                    <strong>Note:</strong> This OTP will expire in 10 minutes. If you didn't request this login, please ignore this email and secure your account.
                </p>
            </div>
        </body>
        </html>
        """

        # Plain text version
        text_content = f"""
        Hello {recipient_name},

        You have requested to login to your account. Use the OTP code below to complete your login:

        OTP: {otp_code}

        This OTP will expire in 10 minutes. If you didn't request this login, please ignore this email and secure your account.
        """

        payload = {
            "sender": {
                "name": self.sender_name,
                "email": self.sender_email
            },
            "to": [
                {
                    "email": recipient_email,
                    "name": recipient_name
                }
            ],
            "subject": "Your Login OTP",
            "htmlContent": html_content,
            "textContent": text_content
        }

        headers = {
            "accept": "application/json",
            "api-key": self.api_key,
            "content-type": "application/json"
        }

        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    BREVO_API_URL,
                    json=payload,
                    headers=headers
                )

                if response.status_code == 201:
                    logger.info(
                        f"Login OTP email sent successfully to {recipient_email}"
                    )
                    return True
                else:
                    logger.error(
                        f"Failed to send login OTP email. "
                        f"Status: {response.status_code}, "
                        f"Response: {response.text}"
                    )
                    return False

        except httpx.TimeoutException:
            logger.error("Timeout while sending login OTP email via Brevo API")
            return False
        except httpx.RequestError as e:
            logger.error(f"Request error while sending login OTP email: {str(e)}")
            return False
        except Exception as e:
            logger.error(f"Unexpected error while sending login OTP email: {str(e)}")
            return False


# Global instance
email_service = EmailService()

