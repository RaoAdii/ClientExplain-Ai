from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    LAWYER = "lawyer"
    REVIEWER = "reviewer"


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str


class FirmRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


class SessionRead(BaseModel):
    profile: ProfileRead
    firm: FirmRead
    role: Role
