from uuid import uuid4

import pytest
from app.core.auth import DEV_FIRM, DEV_USER
from app.db.session import engine
from app.models.entities import Base
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError


@pytest.fixture
def db():
    with engine.connect() as connection:
        with connection.begin() as transaction:
            yield connection
            transaction.rollback()


def insert(db, table, **values):
    values.setdefault("id", uuid4())
    columns = ", ".join(values)
    binds = ", ".join(":" + name for name in values)
    return (
        db.execute(text(f"INSERT INTO {table} ({columns}) VALUES ({binds}) RETURNING *"), values)
        .mappings()
        .one()
    )


def project(db, **values):
    return insert(
        db,
        "projects",
        firm_id=DEV_FIRM,
        created_by=DEV_USER,
        name="Workflow",
        jurisdiction="",
        description="",
        review_status="requires_review",
        **values,
    )


def document(db, project_id):
    return insert(
        db,
        "documents",
        firm_id=DEV_FIRM,
        project_id=project_id,
        filename="input.txt",
        storage_key=str(uuid4()),
        media_type="text/plain",
        byte_size=10,
        sha256="a" * 64,
    )


@pytest.mark.parametrize(
    ("table", "fields"),
    [
        (
            "projects",
            "legal_area language target_audience complexity owner_id workflow_status processing_status",
        ),
        (
            "documents",
            "filename sha256 metadata page_count parsing_error ocr_required deleted_at deleted_by",
        ),
        (
            "document_chunks",
            "page_number heading token_start token_end char_start char_end source_filename metadata embedding_provider",
        ),
        (
            "legal_sources",
            "source_type citation_reference effective_date repeal_date verification_status last_verified_at metadata project_id document_id",
        ),
        ("source_chunks", "page_number heading metadata embedding_provider"),
        (
            "process_stages",
            "responsible_party required_documents estimated_duration source_backed general_explanation limitations verification_status visual_prompt",
        ),
        ("stage_citations", "document_chunk_id source_chunk_id claim_text validation_status"),
        (
            "generation_jobs",
            "kind current_stage progress error_message retry_count idempotency_key request_hash request_metadata started_at finished_at",
        ),
        ("project_versions", "generation_job_id snapshot"),
    ],
)
def test_workflow_fields_are_persisted(db, table, fields):
    required = set(fields.split())
    assert required <= {c["name"] for c in inspect(db).get_columns(table)}
    assert required <= set(Base.metadata.tables[table].columns.keys())


def test_project_document_and_source_defaults(db):
    first = project(db)
    assert (first["owner_id"], first["workflow_status"], first["processing_status"]) == (
        DEV_USER,
        "draft",
        "idle",
    )
    doc = document(db, first["id"])
    assert (doc["status"], doc["metadata"], doc["ocr_required"], doc["deleted_at"]) == (
        "pending",
        {},
        False,
        None,
    )
    with pytest.raises(IntegrityError, match="uq_documents_project_sha256"), db.begin_nested():
        document(db, first["id"])
    document(db, project(db)["id"])
    source = insert(
        db,
        "legal_sources",
        firm_id=DEV_FIRM,
        title="Reference",
        url="",
        jurisdiction="",
        project_id=first["id"],
        document_id=doc["id"],
    )
    assert (source["verification_status"], source["metadata"]) == ("unverified", {})
    with pytest.raises(IntegrityError), db.begin_nested():
        db.execute(
            text("UPDATE legal_sources SET project_id=:project WHERE id=:source"),
            {"project": project(db)["id"], "source": source["id"]},
        )


def test_roles_and_jobs(db):
    for role in ("owner", "admin", "lawyer", "reviewer", "member"):
        profile = insert(db, "profiles", display_name="Member")
        fields = dict(firm_id=DEV_FIRM, profile_id=profile["id"], role=role)
        if role == "member":
            with pytest.raises(IntegrityError), db.begin_nested():
                insert(db, "firm_members", **fields)
        else:
            insert(db, "firm_members", **fields)

    fields = dict(firm_id=DEV_FIRM, project_id=project(db)["id"], kind="analysis")
    job = insert(db, "generation_jobs", idempotency_key="submission", **fields)
    assert (job["status"], job["progress"], job["retry_count"], job["request_metadata"]) == (
        "queued",
        0,
        0,
        {},
    )
    for status in ("queued", "running"):
        with (
            pytest.raises(IntegrityError, match="uq_generation_jobs_active_analysis"),
            db.begin_nested(),
        ):
            insert(db, "generation_jobs", status=status, **fields)
    for status in ("completed", "cancelled", "failed"):
        insert(db, "generation_jobs", status=status, **fields)
    for constraint, invalid in (
        ("ck_generation_jobs_status", {"status": "pending"}),
        ("ck_generation_jobs_status", {"status": "succeeded"}),
        ("ck_generation_jobs_progress", {"progress": -1}),
        ("ck_generation_jobs_progress", {"progress": 101}),
        ("ck_generation_jobs_retry_count", {"retry_count": -1}),
        ("uq_generation_jobs_submission", {"status": "completed", "idempotency_key": "submission"}),
    ):
        with pytest.raises(IntegrityError, match=constraint), db.begin_nested():
            insert(db, "generation_jobs", **{**fields, "status": "completed", **invalid})
    insert(db, "generation_jobs", **{**fields, "kind": "parse"})
    insert(db, "generation_jobs", **{**fields, "project_id": project(db)["id"]})


def test_citation_requires_one_real_tenant_scoped_chunk(db):
    pid = project(db)["id"]
    doc = document(db, pid)
    chunk = insert(
        db,
        "document_chunks",
        firm_id=DEV_FIRM,
        document_id=doc["id"],
        position=0,
        content="Evidence",
    )
    source = insert(db, "legal_sources", firm_id=DEV_FIRM, title="Source", url="", jurisdiction="", project_id=pid)
    other = insert(
        db,
        "source_chunks",
        firm_id=DEV_FIRM,
        source_id=source["id"],
        position=0,
        content="Reference",
    )
    stage = insert(
        db,
        "process_stages",
        firm_id=DEV_FIRM,
        project_id=pid,
        position=0,
        title="Stage",
        explanation="Review",
    )
    assert (stage["source_backed"], stage["verification_status"]) == (False, "unverified")
    fields = dict(stage_id=stage["id"], firm_id=DEV_FIRM, excerpt="Evidence", claim_text="Claim")
    for targets in ({}, {"document_chunk_id": chunk["id"], "source_chunk_id": other["id"]}):
        with (
            pytest.raises(IntegrityError, match="ck_stage_citations_one_target"),
            db.begin_nested(),
        ):
            insert(db, "stage_citations", **fields, **targets)
    insert(db, "stage_citations", source_chunk_id=other["id"], **fields)
    cite = insert(db, "stage_citations", document_chunk_id=chunk["id"], **fields)
    assert cite["validation_status"] == "unverified"
    db.execute(text("DELETE FROM documents WHERE id=:id"), {"id": doc["id"]})
    assert not db.scalar(
        text("SELECT EXISTS(SELECT FROM stage_citations WHERE id=:id)"), {"id": cite["id"]}
    )


@pytest.mark.parametrize(("kind", "scope", "valid"), [
    ("document", "other", False),
    ("source", "other", False),
    ("source", "firm-unverified", False),
    ("source", "firm-verified", True),
])
def test_citations_enforce_project_provenance(db, kind, scope, valid):
    first, second = project(db)["id"], project(db)["id"]
    stage = insert(db, "process_stages", firm_id=DEV_FIRM, project_id=first,
                   position=0, title="Review", explanation="Review")
    if kind == "document":
        doc = document(db, second)
        chunk = insert(db, "document_chunks", firm_id=DEV_FIRM, document_id=doc["id"],
                       position=0, content="Evidence")
        target = {"document_chunk_id": chunk["id"]}
    else:
        source = insert(db, "legal_sources", firm_id=DEV_FIRM, title="Reference", url="",
                        jurisdiction="", project_id=second if scope == "other" else None,
                        verification_status="unverified" if scope == "firm-unverified" else "verified")
        chunk = insert(db, "source_chunks", firm_id=DEV_FIRM, source_id=source["id"],
                       position=0, content="Evidence")
        target = {"source_chunk_id": chunk["id"]}
    fields = dict(firm_id=DEV_FIRM, stage_id=stage["id"], excerpt="Evidence", **target)
    if valid:
        insert(db, "stage_citations", **fields)
        with pytest.raises(IntegrityError), db.begin_nested():
            db.execute(text("UPDATE legal_sources SET verification_status='unverified' WHERE id=:id"),
                       {"id": source["id"]})
    else:
        with pytest.raises(IntegrityError), db.begin_nested():
            insert(db, "stage_citations", **fields)


@pytest.mark.parametrize("table", ["document_chunks", "source_chunks"])
def test_chunk_vector_shape_and_cosine_index(db, table):
    assert (
        db.scalar(
            text("""
        SELECT format_type(atttypid, atttypmod) FROM pg_attribute
        WHERE attrelid=CAST(:table AS regclass) AND attname='embedding'
    """),
            {"table": table},
        )
        == "vector(1536)"
    )
    indexes = inspect(db).get_indexes(table)
    assert any(
        i["dialect_options"].get("postgresql_ops") == {"embedding": "vector_cosine_ops"}
        for i in indexes
    )


def test_new_foreign_keys_include_firm(db):
    expected = {
        "stage_citations": {("document_chunk_id", "firm_id")},
        "legal_sources": {("project_id", "firm_id"), ("document_id", "project_id", "firm_id")},
        "project_versions": {("generation_job_id", "project_id", "firm_id")},
    }
    for table, keys in expected.items():
        assert keys <= {
            tuple(c["constrained_columns"]) for c in inspect(db).get_foreign_keys(table)
        }


def test_version_snapshot_is_immutable(db):
    version = insert(
        db,
        "project_versions",
        project_id=project(db)["id"],
        firm_id=DEV_FIRM,
        snapshot='{"process_name":"Example","review_required":true}',
        version=1,
    )
    with pytest.raises(IntegrityError, match="immutable"), db.begin_nested():
        db.execute(
            text("UPDATE project_versions SET snapshot='{}' WHERE id=:id"), {"id": version["id"]}
        )


def test_workflow_tables_keep_rls_policies_and_update_triggers(db):
    tables = set(Base.metadata.tables)
    covered = db.scalars(
        text("""
        SELECT c.relname FROM pg_class c
        WHERE c.relnamespace='public'::regnamespace AND c.relrowsecurity AND c.relforcerowsecurity
          AND EXISTS (SELECT FROM pg_policy p WHERE p.polrelid=c.oid)
          AND EXISTS (SELECT FROM pg_trigger t WHERE t.tgrelid=c.oid
                      AND t.tgname='update_timestamp' AND t.tgenabled='O')
    """)
    ).all()
    assert tables <= set(covered)
    item = project(db, updated_at="2000-01-01")
    updated = db.scalar(
        text("UPDATE projects SET legal_area='civil' WHERE id=:id RETURNING updated_at"),
        {"id": item["id"]},
    )
    assert updated > item["updated_at"]
