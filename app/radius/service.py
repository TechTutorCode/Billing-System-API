"""
FreeRADIUS user management service.

Uses the RADIUS database only (RadiusSessionLocal). Each operation opens its own
session, commits, and closes. Billing DB is never used here.
Never logs plaintext passwords.
"""

import logging
from typing import List, Optional

from sqlalchemy.orm import Session
from sqlalchemy import and_

from app.radius.database import RadiusSessionLocal
from app.radius.models import Nas, Radcheck, Radreply, Radusergroup

logger = logging.getLogger(__name__)

# FreeRADIUS attribute names
ATTR_CLEARTEXT_PASSWORD = "Cleartext-Password"
ATTR_AUTH_TYPE = "Auth-Type"
ATTR_AUTH_TYPE_REJECT = "Reject"
OP_ASSIGN = ":="
ATTR_WISPR_BANDWIDTH_MAX_DOWN = "WISPr-Bandwidth-Max-Down"
ATTR_WISPR_BANDWIDTH_MAX_UP = "WISPr-Bandwidth-Max-Up"


class RadiusService:
    """Service for RADIUS user lifecycle. Uses RADIUS DB only (RadiusSessionLocal)."""

    @staticmethod
    def create_user(
        username: str,
        password: str,
        groupname: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """
        Create a RADIUS user in the RADIUS database (Cleartext-Password in radcheck).
        Optionally assign to a group. Uses its own RADIUS session.
        """
        db = RadiusSessionLocal()
        try:
            RadiusService._create_user_impl(db, username, password, groupname, priority)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _create_user_impl(
        db: Session,
        username: str,
        password: str,
        groupname: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        row = Radcheck(
            username=username.strip(),
            attribute=ATTR_CLEARTEXT_PASSWORD,
            op=OP_ASSIGN,
            value=password,
        )
        db.add(row)
        db.flush()
        if groupname and groupname.strip():
            RadiusService._assign_group_impl(db, username.strip(), groupname.strip(), priority)
        logger.info("RADIUS user created", extra={"username": username, "has_password": True})

    @staticmethod
    def update_password(username: str, new_password: str) -> None:
        """Update password for a RADIUS user. Uses its own RADIUS session."""
        db = RadiusSessionLocal()
        try:
            RadiusService._update_password_impl(db, username, new_password)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _update_password_impl(db: Session, username: str, new_password: str) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        username = username.strip()
        row = (
            db.query(Radcheck)
            .filter(
                and_(
                    Radcheck.username == username,
                    Radcheck.attribute == ATTR_CLEARTEXT_PASSWORD,
                )
            )
            .first()
        )
        if not row:
            RadiusService._create_user_impl(db, username, new_password)
            return
        row.value = new_password
        db.flush()
        logger.info("RADIUS password updated", extra={"username": username})

    @staticmethod
    def suspend_user(username: str) -> None:
        """Soft-suspend user (Auth-Type := Reject). Uses its own RADIUS session."""
        db = RadiusSessionLocal()
        try:
            RadiusService._suspend_user_impl(db, username)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _suspend_user_impl(db: Session, username: str) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        username = username.strip()
        existing = (
            db.query(Radcheck)
            .filter(
                and_(
                    Radcheck.username == username,
                    Radcheck.attribute == ATTR_AUTH_TYPE,
                    Radcheck.value == ATTR_AUTH_TYPE_REJECT,
                )
            )
            .first()
        )
        if existing:
            logger.info("RADIUS user already suspended", extra={"username": username})
            return
        row = Radcheck(
            username=username,
            attribute=ATTR_AUTH_TYPE,
            op=OP_ASSIGN,
            value=ATTR_AUTH_TYPE_REJECT,
        )
        db.add(row)
        db.flush()
        logger.info("RADIUS user suspended", extra={"username": username})

    @staticmethod
    def unsuspend_user(username: str) -> None:
        """Remove Auth-Type := Reject. Uses its own RADIUS session."""
        db = RadiusSessionLocal()
        try:
            RadiusService._unsuspend_user_impl(db, username)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _unsuspend_user_impl(db: Session, username: str) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        username = username.strip()
        deleted = (
            db.query(Radcheck)
            .filter(
                and_(
                    Radcheck.username == username,
                    Radcheck.attribute == ATTR_AUTH_TYPE,
                    Radcheck.value == ATTR_AUTH_TYPE_REJECT,
                )
            )
            .delete()
        )
        db.flush()
        if deleted:
            logger.info("RADIUS user unsuspended", extra={"username": username})

    @staticmethod
    def delete_user(username: str) -> None:
        """Remove user from radcheck, radreply, radusergroup. Uses its own RADIUS session."""
        db = RadiusSessionLocal()
        try:
            RadiusService._delete_user_impl(db, username)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _delete_user_impl(db: Session, username: str) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        username = username.strip()
        db.query(Radcheck).filter(Radcheck.username == username).delete()
        db.query(Radreply).filter(Radreply.username == username).delete()
        db.query(Radusergroup).filter(Radusergroup.username == username).delete()
        db.flush()
        logger.info("RADIUS user deleted", extra={"username": username})

    @staticmethod
    def ensure_user(
        username: str,
        password: str,
        groupname: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        """
        Ensure radcheck has Cleartext-Password for username; create if missing.
        Remove Auth-Type Reject if present. Uses its own RADIUS session.
        """
        db = RadiusSessionLocal()
        try:
            RadiusService._ensure_user_impl(db, username, password, groupname, priority)
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _ensure_user_impl(
        db: Session,
        username: str,
        password: str,
        groupname: Optional[str] = None,
        priority: int = 0,
    ) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        username = username.strip()
        RadiusService._unsuspend_user_impl(db, username)
        row = (
            db.query(Radcheck)
            .filter(
                and_(
                    Radcheck.username == username,
                    Radcheck.attribute == ATTR_CLEARTEXT_PASSWORD,
                )
            )
            .first()
        )
        if not row:
            RadiusService._create_user_impl(db, username, password, groupname=groupname, priority=priority)
        else:
            row.value = password
            db.flush()
            if groupname and groupname.strip():
                RadiusService._assign_group_impl(db, username, groupname.strip(), priority)
        logger.info("RADIUS user ensured", extra={"username": username})

    @staticmethod
    def set_reply_attributes(
        username: str,
        download_bps: Optional[int] = None,
        upload_bps: Optional[int] = None,
        extra_attributes: Optional[List[tuple]] = None,
    ) -> None:
        """Set radreply attributes (e.g. rate limits). Uses its own RADIUS session."""
        db = RadiusSessionLocal()
        try:
            RadiusService._set_reply_attributes_impl(
                db, username, download_bps, upload_bps, extra_attributes
            )
            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    @staticmethod
    def _set_reply_attributes_impl(
        db: Session,
        username: str,
        download_bps: Optional[int],
        upload_bps: Optional[int],
        extra_attributes: Optional[List[tuple]],
    ) -> None:
        if not username or not username.strip():
            raise ValueError("RADIUS username is required")
        username = username.strip()
        to_set: List[tuple] = []
        if download_bps is not None:
            to_set.append((ATTR_WISPR_BANDWIDTH_MAX_DOWN, str(download_bps)))
        if upload_bps is not None:
            to_set.append((ATTR_WISPR_BANDWIDTH_MAX_UP, str(upload_bps)))
        if extra_attributes:
            to_set.extend(extra_attributes)
        for attr, value in to_set:
            row = (
                db.query(Radreply)
                .filter(
                    and_(
                        Radreply.username == username,
                        Radreply.attribute == attr,
                    )
                )
                .first()
            )
            if row:
                row.value = value
            else:
                db.add(
                    Radreply(username=username, attribute=attr, op="=", value=value)
                )
        db.flush()
        if to_set:
            logger.info(
                "RADIUS reply attributes set",
                extra={"username": username, "attributes": [a[0] for a in to_set]},
            )

    @staticmethod
    def _assign_group_impl(db: Session, username: str, groupname: str, priority: int = 0) -> None:
        if not username or not username.strip() or not groupname or not groupname.strip():
            raise ValueError("username and groupname are required")
        username = username.strip()
        groupname = groupname.strip()
        existing = (
            db.query(Radusergroup)
            .filter(
                and_(
                    Radusergroup.username == username,
                    Radusergroup.groupname == groupname,
                )
            )
            .first()
        )
        if existing:
            existing.priority = priority
        else:
            db.add(
                Radusergroup(username=username, groupname=groupname, priority=priority)
            )
        db.flush()
        logger.info(
            "RADIUS user group assigned",
            extra={"username": username, "groupname": groupname},
        )

    @staticmethod
    def add_nas(nasname: str, shortname: str, secret: str) -> None:
        """
        Register a NAS (router) in the RADIUS database so FreeRADIUS trusts it.
        Uses its own RADIUS session. Never logs the secret.

        Args:
            nasname: NAS IP address (e.g. router VPN IP).
            shortname: Short name / identifier (e.g. router name).
            secret: Shared secret (must match MikroTik RADIUS client config).
        """
        if not nasname or not shortname or not secret:
            raise ValueError("nasname, shortname, and secret are required")
        db = RadiusSessionLocal()
        try:
            existing = (
                db.query(Nas)
                .filter(Nas.nasname == nasname.strip(), Nas.shortname == shortname.strip())
                .first()
            )
            if existing:
                existing.secret = secret
                existing.type = "other"
            else:
                db.add(
                    Nas(
                        nasname=nasname.strip(),
                        shortname=shortname.strip(),
                        type="other",
                        secret=secret,
                    )
                )
            db.commit()
            logger.info(
                "RADIUS NAS registered",
                extra={"nasname": nasname, "shortname": shortname},
            )
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()


radius_service = RadiusService()
