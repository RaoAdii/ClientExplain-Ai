from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

JobStatus = Literal["queued", "running", "completed", "failed", "cancelled"]
JobType = Literal["parse", "analysis"]


class JobRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    kind: str
    status: JobStatus
    current_stage: str | None
    progress: int = Field(ge=0, le=100)
    retry_count: int
    error_code: str | None
    error_message: str | None
    created_at: datetime
    updated_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
