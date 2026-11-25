from app.core.auth import Principal, get_principal, tenant_session
from app.models.entities import Firm, Profile
from app.schemas.auth import ProfileUpdate, SessionRead
from app.services.activity import audit
from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.orm import Session

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.get("/me", response_model=SessionRead)
def me(
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    firm = db.get(Firm, principal.firm_id)
    profile = db.get(Profile, principal.user_id)
    if firm is None or profile is None:
        raise HTTPException(401, "Your workspace session is no longer available.")
    return {"profile": profile, "firm": firm, "role": principal.role}


@router.patch("/me", response_model=SessionRead)
def update_me(
    data: ProfileUpdate,
    response: Response,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    profile = db.get(Profile, principal.user_id)
    if profile is None:
        raise HTTPException(401, "Your workspace session is no longer available.")
    if profile.display_name != data.display_name:
        profile.display_name = data.display_name
        audit(db, principal, "profile.updated", profile.id)
    response.headers["Cache-Control"] = "no-store"
    firm = db.get(Firm, principal.firm_id)
    if firm is None:
        raise HTTPException(401, "Your workspace session is no longer available.")
    return {"profile": profile, "firm": firm, "role": principal.role}
