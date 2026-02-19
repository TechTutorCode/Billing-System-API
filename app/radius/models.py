"""
FreeRADIUS PostgreSQL table mappings.

These models map to existing FreeRADIUS tables in the RADIUS database.
They use RadiusBase and radius_engine only (no billing DB).
Tables are NOT created by the application; FreeRADIUS or DBA must create them.
"""

from sqlalchemy import Column, Integer, String, Text

from app.radius.database import RadiusBase


# FreeRADIUS standard schema (raddb/mods-config/sql/main/postgresql/schema.sql)


class Radcheck(RadiusBase):
    """Maps to FreeRADIUS radcheck table (check attributes for authentication)."""

    __tablename__ = "radcheck"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, default="")
    attribute = Column(Text, nullable=False, default="")
    op = Column(String(2), nullable=False, default="==")
    value = Column(Text, nullable=False, default="")


class Radreply(RadiusBase):
    """Maps to FreeRADIUS radreply table (reply attributes, e.g. rate limits)."""

    __tablename__ = "radreply"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, default="")
    attribute = Column(Text, nullable=False, default="")
    op = Column(String(2), nullable=False, default="=")
    value = Column(Text, nullable=False, default="")


class Radusergroup(RadiusBase):
    """Maps to FreeRADIUS radusergroup table (user-to-group mapping)."""

    __tablename__ = "radusergroup"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    username = Column(Text, nullable=False, default="")
    groupname = Column(Text, nullable=False, default="")
    priority = Column(Integer, nullable=False, default=0)


class Nas(RadiusBase):
    """
    Maps to FreeRADIUS nas table (NAS clients trusted by RADIUS).
    Each MikroTik router is registered here so FreeRADIUS accepts its requests.
    """

    __tablename__ = "nas"
    __table_args__ = {"extend_existing": True}

    id = Column(Integer, primary_key=True, autoincrement=True)
    nasname = Column(Text, nullable=False)   # Router IP (e.g. VPN IP)
    shortname = Column(Text, nullable=False) # Router name or identifier
    type = Column(String(30), nullable=False, default="other")
    ports = Column(Integer, nullable=True)
    secret = Column(Text, nullable=False)    # Shared secret (must match MikroTik RADIUS client)
    server = Column(String(64), nullable=True)
    community = Column(String(50), nullable=True)
    description = Column(String(200), nullable=True)
