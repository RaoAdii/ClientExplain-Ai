from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]
Jurisdiction = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Description = ""
    jurisdiction: Jurisdiction = ""


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    description: Description | None = None
    jurisdiction: Jurisdiction | None = None

    @model_validator(mode="after")
    def reject_explicit_null(self):
        if not self.model_fields_set:
            raise ValueError("Provide at least one field to update")
        if any(getattr(self, key) is None for key in self.model_fields_set):
            raise ValueError("Project fields cannot be null")
        return self


class ProjectRead(ProjectCreate):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    review_status: str
    created_at: datetime
    updated_at: datetime
