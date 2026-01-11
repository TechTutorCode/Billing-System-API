"""Router utility functions."""

import secrets
from typing import Optional

from app.auth.utils import hash_password, verify_password


def generate_router_password() -> str:
    """
    Generate a strong random password for router VPN user.

    Returns:
        Random password string (32 characters)
    """
    return secrets.token_urlsafe(24)


def generate_vpn_username(router_id: str) -> str:
    """
    Generate VPN username for router.

    Args:
        router_id: Router UUID as string

    Returns:
        VPN username in format: router_<id>
    """
    # Use first 8 characters of UUID for shorter username
    short_id = router_id.replace("-", "")[:8]
    return f"router_{short_id}"


def encrypt_vpn_password(password: str) -> str:
    """
    Encrypt VPN password using bcrypt.

    Args:
        password: Plain text password

    Returns:
        Encrypted password
    """
    return hash_password(password)


def verify_vpn_password(plain_password: str, encrypted_password: str) -> bool:
    """
    Verify VPN password against encrypted version.

    Args:
        plain_password: Plain text password
        encrypted_password: Encrypted password

    Returns:
        True if password matches
    """
    return verify_password(plain_password, encrypted_password)


def generate_mikrotik_openvpn_config(
    server_ip: str,
    server_port: int,
    username: str,
    password: str,
    protocol: str = "tcp",
    auth: str = "sha1",
    cipher: str = "aes128"
) -> str:
    """
    Generate MikroTik RouterOS OpenVPN client configuration.

    Args:
        server_ip: OpenVPN server IP address
        server_port: OpenVPN server port
        username: VPN username
        password: VPN password
        protocol: Protocol (tcp or udp)
        auth: Authentication algorithm
        cipher: Encryption cipher

    Returns:
        RouterOS CLI configuration string
    """
    config = f"""/interface ovpn-client add \\
    name=ovpn-out1 \\
    connect-to={server_ip} \\
    port={server_port} \\
    mode=ip \\
    protocol={protocol} \\
    auth={auth} \\
    cipher={cipher} \\
    user="{username}" \\
    password="{password}" \\
    add-default-route=no \\
    disabled=no
"""
    return config

