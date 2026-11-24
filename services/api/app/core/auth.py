import hmac
from dataclasses import dataclass
from uuid import UUID, uuid4

import jwt
from app.core.config import settings
from app.db.session import SessionLocal
from app.models.entities import Firm, FirmMember, Profile
from app.schemas.auth import Role
from fastapi import Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select, text

bearer = HTTPBearer(auto_error=False)
DEV_USER = UUID("a1646440-f4de-4b30-821d-2b377800bcad")
DEV_FIRM = UUID("ef050cc1-cfcb-48a7-b8db-7155c1a432e1")
jwks = (
    jwt.PyJWKClient(f"{settings.supabase_url}/auth/v1/.well-known/jwks.json", timeout=5)
    if settings.supabase_url
    else None
)


@dataclass(frozen=True)
class Principal:
    user_id: UUID
    firm_id: UUID
    role: Role


def provision_development_principal() -> Principal:
    with SessionLocal.begin() as db:
        db.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"),
            {"user_id": str(DEV_USER)},
        )
        db.execute(
            text("SELECT set_config('app.firm_id', :firm_id, true)"),
            {"firm_id": str(DEV_FIRM)},
        )
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:subject, 0))"),
            {"subject": str(DEV_USER)},
        )
        if not db.get(Profile, DEV_USER):
            db.add(Profile(id=DEV_USER, display_name="Developer"))
            db.flush()
        if not db.get(Firm, DEV_FIRM):
            db.add(Firm(id=DEV_FIRM, name="Development Workspace"))
            db.flush()
        member = db.scalar(
            select(FirmMember).where(
                FirmMember.profile_id == DEV_USER,
                FirmMember.firm_id == DEV_FIRM,
            )
        )
        if not member:
            db.add(
                FirmMember(
                    profile_id=DEV_USER,
                    firm_id=DEV_FIRM,
                    role="owner",
                )
            )
        return Principal(DEV_USER, DEV_FIRM, Role.OWNER)


def get_principal(credentials: HTTPAuthorizationCredentials | None = Depends(bearer)) -> Principal:
    if not credentials:
        raise HTTPException(
            401, "Sign in to access your workspace", headers={"WWW-Authenticate": "Bearer"}
        )
    token = credentials.credentials
    if settings.auth_mode == "development":
        if not hmac.compare_digest(token, settings.dev_auth_token):
            raise HTTPException(401, "Invalid development session")
        return provision_development_principal()
    try:
        key = jwks.get_signing_key_from_jwt(token)
        claims = jwt.decode(
            token,
            key.key,
            algorithms=["RS256", "ES256"],
            audience="authenticated",
            issuer=f"{settings.supabase_url}/auth/v1",
            options={"require": ["exp", "sub", "aud", "iss"]},
        )
        user_id = UUID(claims["sub"])
    except (jwt.PyJWTError, ValueError, KeyError) as exc:
        raise HTTPException(401, "Your session is invalid or expired. Sign in again.") from exc
    with SessionLocal.begin() as db:
        db.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": str(user_id)}
        )
        # Serialize first-login provisioning across requests for this subject.
        db.execute(
            text("SELECT pg_advisory_xact_lock(hashtextextended(:subject, 0))"),
            {"subject": str(user_id)},
        )
        member = db.scalar(
            select(FirmMember)
            .where(FirmMember.profile_id == user_id)
            .order_by(FirmMember.created_at, FirmMember.id)
            .limit(1)
        )
        if member:
            return Principal(user_id, member.firm_id, Role(member.role))
        if not db.get(Profile, user_id):
            db.add(Profile(id=user_id, display_name="Lawyer"))
            db.flush()
        firm = Firm(id=uuid4(), name="My legal workspace")
        db.execute(
            text("SELECT set_config('app.firm_id', :firm_id, true)"), {"firm_id": str(firm.id)}
        )
        db.add(firm)
        db.flush()
        db.add(FirmMember(profile_id=user_id, firm_id=firm.id, role="owner"))
        return Principal(user_id, firm.id, Role.OWNER)


def tenant_session(principal: Principal = Depends(get_principal)):
    with SessionLocal.begin() as db:
        db.execute(
            text("SELECT set_config('app.firm_id', :firm_id, true)"),
            {"firm_id": str(principal.firm_id)},
        )
        db.execute(
            text("SELECT set_config('app.user_id', :user_id, true)"),
            {"user_id": str(principal.user_id)},
        )
        yield db
