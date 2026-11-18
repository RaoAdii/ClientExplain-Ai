from uuid import uuid4

import pytest
from app.core.auth import DEV_FIRM, DEV_USER
from app.db.session import engine
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


def test_rls_hides_rows_without_tenant_and_filters_other_tenant():
    # This role and all records are rolled back, leaving no test grants behind.
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            connection.execute(text("CREATE ROLE ce_test_rls NOLOGIN NOBYPASSRLS"))
            connection.execute(text("GRANT USAGE ON SCHEMA public TO ce_test_rls"))
            connection.execute(text("GRANT SELECT ON projects TO ce_test_rls"))
            project_id = uuid4()
            connection.execute(
                text(
                    "INSERT INTO projects (id, firm_id, created_by, name, description, jurisdiction, review_status) VALUES (:id, :firm, :user, 'RLS test', '', '', 'requires_review')"
                ),
                {"id": project_id, "firm": DEV_FIRM, "user": DEV_USER},
            )
            connection.execute(text("SET LOCAL ROLE ce_test_rls"))
            assert connection.scalar(text("SELECT count(*) FROM projects")) == 0
            connection.execute(
                text("SELECT set_config('app.firm_id', :firm, true)"), {"firm": str(uuid4())}
            )
            assert connection.scalar(text("SELECT count(*) FROM projects")) == 0
            connection.execute(
                text("SELECT set_config('app.firm_id', :firm, true)"), {"firm": str(DEV_FIRM)}
            )
            assert (
                connection.scalar(
                    text("SELECT count(*) FROM projects WHERE id = :id"), {"id": project_id}
                )
                == 1
            )
        finally:
            transaction.rollback()


def test_document_cannot_reference_other_firm_project():
    with engine.connect() as connection:
        transaction = connection.begin()
        try:
            project_id, firm_id = uuid4(), uuid4()
            connection.execute(
                text("INSERT INTO firms(id, name) VALUES (:id, 'Other tenant')"), {"id": firm_id}
            )
            connection.execute(
                text(
                    "INSERT INTO projects (id, firm_id, created_by, name, description, jurisdiction, review_status) VALUES (:id, :firm, :user, 'Constraint test', '', '', 'requires_review')"
                ),
                {"id": project_id, "firm": DEV_FIRM, "user": DEV_USER},
            )
            with pytest.raises(IntegrityError, match="documents_project_id_firm_id_fkey"):
                connection.execute(
                    text(
                        "INSERT INTO documents (id, firm_id, project_id, filename, storage_key, media_type, byte_size, status, sha256) VALUES (:id, :firm, :project, 'test.txt', :key, 'text/plain', 10, 'pending', repeat('a', 64))"
                    ),
                    {"id": uuid4(), "firm": firm_id, "project": project_id, "key": str(uuid4())},
                )
        finally:
            transaction.rollback()
