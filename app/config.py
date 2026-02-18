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
        # Database settings (billing application only)
        self.DATABASE_URL: str = os.getenv(
            "DATABASE_URL",
            "postgresql://postgres:deno0707@37.60.242.201:5432/billing_system"
        )
# postgresql://radius_user:strongpassword@37.60.242.201:5432/billing_system
        # RADIUS database (separate PostgreSQL; FreeRADIUS tables only)
        self.RADIUS_DATABASE_URL: str = os.getenv(
            "RADIUS_DATABASE_URL",
            "postgresql://radius_user:strongpassword@37.60.242.201:5432/radius"
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
        jwt_access_expire = os.getenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "60")
        self.JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = int(jwt_access_expire) if jwt_access_expire else 60  # 1 hour
        jwt_refresh_expire = os.getenv("JWT_REFRESH_TOKEN_EXPIRE_DAYS", "30")
        self.JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = int(jwt_refresh_expire) if jwt_refresh_expire else 30  # 30 days

        # OpenVPN settings
        self.OPENVPN_SERVER_IP: str = os.getenv("OPENVPN_SERVER_IP", "37.60.242.201")
        openvpn_port = os.getenv("OPENVPN_SERVER_PORT", "1194")
        self.OPENVPN_SERVER_PORT: int = int(openvpn_port) if openvpn_port else 1194
        self.OPENVPN_STATUS_LOG: str = os.getenv("OPENVPN_STATUS_LOG", "/var/log/openvpn-status.log")

        # SSH settings for host machine access
        # Default to actual server IP address
        # Alternative options:
        # - host.docker.internal (with extra_hosts in docker-compose)
        # - 172.17.0.1 (Docker bridge gateway on Linux)
        self.SSH_HOST: str = os.getenv("SSH_HOST", "37.60.242.201")
        self.SSH_USER: str = os.getenv("SSH_USER", "root")
        self.SSH_PASSWORD: str = os.getenv("SSH_PASSWORD", "nexgen2025")
        # SSH key path (optional, used only if password is not provided)
        self.SSH_KEY_PATH: str = os.getenv("SSH_KEY_PATH", "")
        ssh_port = os.getenv("SSH_PORT", "22")
        self.SSH_PORT: int = int(ssh_port) if ssh_port else 22
        ssh_strict_check = os.getenv("SSH_STRICT_HOST_KEY_CHECKING", "no")
        self.SSH_STRICT_HOST_KEY_CHECKING: str = ssh_strict_check if ssh_strict_check else "no"

        # FreeRADIUS: default group for radusergroup (optional)
        self.RADIUS_DEFAULT_GROUP: str = os.getenv("RADIUS_DEFAULT_GROUP", "users")


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()

