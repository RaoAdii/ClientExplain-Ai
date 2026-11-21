from app.core.auth import Principal, get_principal, tenant_session
from app.models.entities import Firm, Profile
from app.schemas.auth import SessionRead
from fastapi import APIRouter, Depends, HTTPException
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
