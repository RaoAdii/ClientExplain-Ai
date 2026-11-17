"""Idempotent local identity only; never seed fabricated project data."""

from app.core.auth import DEV_FIRM, DEV_USER
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import Firm, FirmMember, Profile
from sqlalchemy import select

if settings.auth_mode != "development" or settings.app_env == "production":
    raise SystemExit("Development seed is disabled outside development authentication")

with SessionLocal.begin() as db:
    if not db.get(Profile, DEV_USER):
        db.add(Profile(id=DEV_USER, display_name="Local developer"))
    if not db.get(Firm, DEV_FIRM):
        db.add(Firm(id=DEV_FIRM, name="Local development workspace"))
    db.flush()
    if not db.scalar(
        select(FirmMember).where(FirmMember.profile_id == DEV_USER, FirmMember.firm_id == DEV_FIRM)
    ):
        db.add(FirmMember(profile_id=DEV_USER, firm_id=DEV_FIRM, role="owner"))
print("Development identity ready; no projects were seeded.")
