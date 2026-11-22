from uuid import UUID

from app.core.auth import Principal, get_principal, tenant_session
from app.core.permissions import PROJECT_EDITORS, check_roles
from app.core.rate_limits import rate_limit
from app.schemas.documents import DocumentRead, UploadRead
from app.schemas.workflow import DocumentDetail, ErrorRead, ValidationErrorRead
from app.services.documents import delete_document, document_detail, list_documents, upload_document
from app.services.projects import require_project
from fastapi import APIRouter, Depends, File, HTTPException, Request, Response, UploadFile
from sqlalchemy.orm import Session

router = APIRouter(
    tags=["Documents"],
    responses={
        401: {"model": ErrorRead},
        404: {"model": ErrorRead},
        422: {"model": ValidationErrorRead},
    },
)


async def strict_upload(request: Request):
    form = await request.form()
    if set(form) != {"file"} or len(form.getlist("file")) != 1:
        raise HTTPException(422, "Submit exactly one file and no unknown fields.")


@router.post(
    "/projects/{project_id}/documents",
    response_model=UploadRead,
    status_code=202,
    dependencies=[Depends(strict_upload)],
    responses={
        **{code: {"model": ErrorRead} for code in (403, 409, 413, 415, 429, 503)},
        422: {"model": ValidationErrorRead | ErrorRead},
    },
)
def upload(
    project_id: UUID,
    response: Response,
    file: UploadFile = File(),
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    require_project(db, principal, project_id)
    check_roles(principal, *PROJECT_EDITORS)
    rate_limit(principal, "upload", response)
    return upload_document(principal, project_id, file)


@router.get("/projects/{project_id}/documents", response_model=list[DocumentRead])
def index(
    project_id: UUID,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return list_documents(db, principal, project_id)


@router.get(
    "/documents/{document_id}", response_model=DocumentDetail, responses={503: {"model": ErrorRead}}
)
def show(
    document_id: UUID,
    download: bool = False,
    principal: Principal = Depends(get_principal),
    db: Session = Depends(tenant_session, scope="function"),
):
    return document_detail(db, principal, document_id, download=download)


@router.delete(
    "/documents/{document_id}",
    status_code=204,
    responses={code: {"model": ErrorRead} for code in (403, 503)},
)
def delete(document_id: UUID, principal: Principal = Depends(get_principal)):
    delete_document(principal, document_id)
    return Response(status_code=204)
