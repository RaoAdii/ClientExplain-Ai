from datetime import datetime
from uuid import UUID

from app.schemas.jobs import JobRead
from pydantic import BaseModel, ConfigDict


class DocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    project_id: UUID
    filename: str
    media_type: str
    byte_size: int
    sha256: str
    status: str
    created_at: datetime
    updated_at: datetime


class UploadRead(BaseModel):
    document: DocumentRead
    job: JobRead
