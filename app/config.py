"""Configuration management using environment variables."""

import os
from functools import lru_cache

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


class Settings:
    """Application settings loaded from environment variables."""

    def __init__(self):
        """Initialize settings from environment variables."""
        # Database settings
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "postgresql://user:password@localhost:5432/billing_system"
        )

        # Brevo (Sendinblue) API settings
        self.BREVO_API_KEY: str = os.getenv("BREVO_API_KEY", "")
        self.BREVO_SENDER_EMAIL: str = os.getenv("BREVO_SENDER_EMAIL", "")
        self.BREVO_SENDER_NAME: str = os.getenv("BREVO_SENDER_NAME", "Billing System")

        # Frontend URL for verification links
        self.FRONTEND_VERIFY_URL: str = os.getenv(
            "FRONTEND_VERIFY_URL",
            "http://localhost:3000/verify-email"
        )

        # Application settings
        self.DEBUG: bool = os.getenv("DEBUG", "False").lower() == "true"

        # Cloudinary settings
        self.CLOUDINARY_CLOUD_NAME: str = os.getenv("CLOUDINARY_CLOUD_NAME")
        self.CLOUDINARY_API_KEY: str = os.getenv("CLOUDINARY_API_KEY")
        self.CLOUDINARY_API_SECRET: str = os.getenv("CLOUDINARY_API_SECRET")

        # JWT settings
        self.JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "")
        self.JWT_REFRESH_SECRET_KEY: str = os.getenv("JWT_REFRESH_SECRET_KEY", self.JWT_SECRET_KEY)  # Defaults to same as access token key
        self.JWT_ALGORITHM: str = os.getenv("JWT_ALGORITHM", "HS256")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60"))  # 1 hour
        self.JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30"))  # 30 days

        # OpenVPN settings
        self.OPENVPN_SERVER_IP: str = os.getenv("OPENVPN_SERVER_IP", "")
        self.OPENVPN_SERVER_PORT: int = int(os.getenv("OPENVPN_SERVER_PORT", "1194"))


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

