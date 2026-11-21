from app.core.auth import Principal, get_principal
from app.schemas.auth import Role
from app.schemas.projects import ReviewStatus
from fastapi import Depends, HTTPException

PROJECT_EDITORS = (Role.OWNER, Role.ADMIN, Role.LAWYER)
PROJECT_MANAGERS = (Role.OWNER, Role.ADMIN)


def check_roles(principal: Principal, *roles: Role) -> None:
    if principal.role not in roles:
        raise HTTPException(403, "Your role does not permit this operation.")


def require_roles(*roles: Role):
    def authorize(principal: Principal = Depends(get_principal)) -> Principal:
        check_roles(principal, *roles)
        return principal

    return authorize


def can_transition_review(role: Role, old: ReviewStatus, new: ReviewStatus) -> bool:
    if role in (Role.OWNER, Role.ADMIN, Role.REVIEWER):
        return True
    return role == Role.LAWYER and old == "requires_review" and new == "in_review"
