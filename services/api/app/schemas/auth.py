from enum import StrEnum
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints

DisplayName = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]


class Role(StrEnum):
    OWNER = "owner"
    ADMIN = "admin"
    LAWYER = "lawyer"
    REVIEWER = "reviewer"


class ProfileRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    display_name: str


class ProfileUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: DisplayName


class FirmRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    name: str


class SessionRead(BaseModel):
    profile: ProfileRead
    firm: FirmRead
    role: Role
