from datetime import datetime
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, StringConstraints, model_validator

Name = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]
Description = Annotated[str, StringConstraints(strip_whitespace=True, max_length=10000)]
Jurisdiction = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
LegalArea = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Language = Annotated[str, StringConstraints(strip_whitespace=True, max_length=60)]
Audience = Annotated[str, StringConstraints(strip_whitespace=True, max_length=120)]
Complexity = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=40)]
WorkflowStatus = Literal["draft", "active", "archived"]
ProcessingStatus = Literal["idle", "queued", "running", "completed", "failed", "cancelled"]
ReviewStatus = Literal["requires_review", "in_review", "approved"]


class ProjectCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name
    description: Description = ""
    jurisdiction: Jurisdiction = ""
    legal_area: LegalArea = ""
    language: Language = ""
    target_audience: Audience = ""
    complexity: Complexity = "unspecified"
    workflow_status: WorkflowStatus = "draft"


class ProjectUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: Name | None = None
    description: Description | None = None
    jurisdiction: Jurisdiction | None = None
    legal_area: LegalArea | None = None
    language: Language | None = None
    target_audience: Audience | None = None
    complexity: Complexity | None = None
    workflow_status: WorkflowStatus | None = None
    review_status: ReviewStatus | None = None

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
    review_status: ReviewStatus
    processing_status: ProcessingStatus
    owner_id: UUID
    created_at: datetime
    updated_at: datetime


class ProjectPage(BaseModel):
    items: list[ProjectRead]
    total: int
    limit: int
    offset: int


class ActivityRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    action: str
    actor_id: UUID | None
    resource_id: UUID
    created_at: datetime
