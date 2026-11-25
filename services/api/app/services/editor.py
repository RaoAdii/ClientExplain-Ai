"""Atomic editor saves using the existing project/stage/version ancestry lock."""

from uuid import UUID

from app.core.auth import Principal
from app.core.permissions import PROJECT_EDITORS, check_roles
from app.models.entities import GenerationJob, ProcessStage, ProjectVersion, StageCitation
from app.schemas.editor import WorkflowRead, WorkflowWrite
from app.services.activity import audit
from app.services.projects import require_project
from fastapi import HTTPException
from sqlalchemy import delete, select
from sqlalchemy.orm import Session

CONTENT_FIELDS = ("title", "explanation", "responsible_party", "required_documents", "limitations")


def latest_version(db: Session, principal: Principal, project_id: UUID):
    return db.scalar(
        select(ProjectVersion)
        .where(ProjectVersion.project_id == project_id, ProjectVersion.firm_id == principal.firm_id)
        .order_by(ProjectVersion.version.desc())
        .limit(1)
    )


def stage_rows(db: Session, principal: Principal, project_id: UUID):
    return list(
        db.scalars(
            select(ProcessStage)
            .where(ProcessStage.project_id == project_id, ProcessStage.firm_id == principal.firm_id)
            .order_by(ProcessStage.position, ProcessStage.id)
        )
    )


def read_workflow(db: Session, principal: Principal, project_id: UUID) -> WorkflowRead:
    project = require_project(db, principal, project_id, for_update=True)
    version = latest_version(db, principal, project_id)
    graph = version.snapshot.get("editor", {}) if version else {}
    details = {item["id"]: item for item in graph.get("stages", [])}
    stages = []
    for index, stage in enumerate(stage_rows(db, principal, project_id)):
        saved = details.get(str(stage.id), {})
        stages.append(
            {
                "id": stage.id,
                **{name: getattr(stage, name) for name in CONTENT_FIELDS},
                "position": saved.get("position", {"x": 40, "y": index * 180}),
                **{key: saved.get(key, []) for key in ("actions", "preconditions", "outcomes")},
                "status": saved.get("status", "pending"),
            }
        )
    ids = {str(stage["id"]) for stage in stages}
    edges = [
        edge for edge in graph.get("edges", []) if edge["source"] in ids and edge["target"] in ids
    ]
    return WorkflowRead(
        version=version.version if version else 0,
        stages=stages,
        edges=edges,
        review_status=project.review_status,
    )


def save_workflow(db: Session, principal: Principal, project_id: UUID, data: WorkflowWrite):
    project = require_project(db, principal, project_id, for_update=True)
    check_roles(principal, *PROJECT_EDITORS)
    version = latest_version(db, principal, project_id)
    if data.version != (version.version if version else 0):
        raise HTTPException(409, "The workflow changed. Reload before saving your changes.")
    active = db.scalar(
        select(GenerationJob.id).where(
            GenerationJob.project_id == project_id,
            GenerationJob.firm_id == principal.firm_id,
            GenerationJob.kind == "analysis",
            GenerationJob.status.in_(["queued", "running"]),
        )
    )
    if active:
        raise HTTPException(409, "Wait for analysis to finish before editing the workflow.")
    existing = {row.id: row for row in stage_rows(db, principal, project_id)}
    incoming = {row.id for row in data.stages}
    new_ids = incoming - existing.keys()
    # Avoid accepting identifiers belonging to any other project, without disclosure.
    if new_ids and db.scalar(select(ProcessStage.id).where(ProcessStage.id.in_(new_ids)).limit(1)):
        raise HTTPException(422, "A stage identifier is unavailable. Create the stage again.")
    for key, row in existing.items():
        if key not in incoming:
            db.delete(row)
        else:
            row.position += 1000
    db.flush()
    for index, stage in enumerate(data.stages):
        values = stage.model_dump(include=set(CONTENT_FIELDS))
        row = existing.get(stage.id)
        if row is None:
            row = ProcessStage(
                id=stage.id,
                project_id=project_id,
                firm_id=principal.firm_id,
                position=index,
                **values,
            )
            db.add(row)
        else:
            changed = any(getattr(row, key) != value for key, value in values.items())
            if changed:
                # Old evidence supports the old wording, not an arbitrary user edit.
                db.execute(
                    delete(StageCitation).where(
                        StageCitation.stage_id == row.id, StageCitation.firm_id == principal.firm_id
                    )
                )
                row.source_backed = False
                row.general_explanation = True
                row.verification_status = "unverified"
                row.estimated_duration = None
            for key, value in values.items():
                setattr(row, key, value)
            row.position = index
    project.review_status = "requires_review"
    snapshot = dict(version.snapshot) if version else {}
    snapshot["editor"] = data.model_dump(mode="json", exclude={"version"})
    db.add(
        ProjectVersion(
            project_id=project_id,
            firm_id=principal.firm_id,
            version=data.version + 1,
            snapshot=snapshot,
        )
    )
    audit(db, principal, "workflow.saved", project_id)
    db.flush()
    return read_workflow(db, principal, project_id)
