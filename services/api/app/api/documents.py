from uuid import UUID

from app.core.auth import Principal, get_principal
from app.schemas.documents import UploadRead
from app.services.documents import upload_document
from fastapi import APIRouter, Depends, File, UploadFile

router = APIRouter(prefix="/projects", tags=["Documents"])


@router.post("/{project_id}/documents", response_model=UploadRead, status_code=202)
def upload(
    project_id: UUID,
    file: UploadFile = File(),
    principal: Principal = Depends(get_principal),
):
    return upload_document(principal, project_id, file)
