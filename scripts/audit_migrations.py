"""Verify Alembic in a disposable local database."""

import os
import subprocess
import sys
from contextlib import contextmanager
from pathlib import Path
from uuid import uuid4

from alembic.config import Config
from alembic.script import ScriptDirectory
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "api"
load_dotenv(REPOSITORY_ROOT / ".env")

AUDIT_DATABASE = "clientexplain_migration_audit_" + uuid4().hex
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is required; run scripts/setup.ps1 first")
admin_url = make_url(database_url).set(database="postgres")
audit_url = make_url(database_url).set(database=AUDIT_DATABASE)
admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")

with admin.connect() as connection:
    connection.execute(text(f'CREATE DATABASE "{AUDIT_DATABASE}"'))

environment = os.environ.copy()
environment["DATABASE_URL"] = audit_url.render_as_string(hide_password=False)
command = [sys.executable, "-m", "alembic", "-c", str(API_ROOT / "alembic.ini")]
expected_head = ScriptDirectory.from_config(
    Config(str(API_ROOT / "alembic.ini"))
).get_current_head()
step1 = "c62fbd003112"
audit = create_engine(audit_url)


def migrate(*arguments):
    subprocess.run([*command, *arguments], env=environment, cwd=REPOSITORY_ROOT, check=True)


def expect_downgrade_refusal(reason):
    attempt = subprocess.run(
        [*command, "downgrade", step1],
        env=environment,
        cwd=REPOSITORY_ROOT,
        capture_output=True,
        text=True,
    )
    assert attempt.returncode != 0 and reason in attempt.stderr, (
        f"Expected rollback refusal: {reason}"
    )


@contextmanager
def tenant_transaction(ids):
    with audit.begin() as connection:
        if use_owner_role:
            connection.execute(text("SET LOCAL ROLE pg_database_owner"))
        assert connection.scalar(text("SELECT row_security_active('firms')"))
        connection.execute(
            text("""
            SELECT set_config('app.firm_id', :firm, true), set_config('app.user_id', :user, true)
        """),
            {"firm": str(ids["firm"]), "user": str(ids["user"])},
        )
        yield connection


try:
    migrate("upgrade", step1)
    with audit.begin() as connection:
        use_owner_role = connection.scalar(
            text("""
            SELECT rolsuper OR rolbypassrls FROM pg_roles WHERE rolname=current_user
        """)
        )
        if use_owner_role:
            # Exercise the policies even when the local migration login is a superuser.
            # This built-in role and these grants are scoped to the disposable database.
            connection.execute(
                text("GRANT SELECT ON ALL TABLES IN SCHEMA public TO pg_database_owner")
            )
            connection.execute(
                text("""
                GRANT INSERT ON firms,profiles,firm_members,projects,documents,document_chunks,
                    generation_jobs,process_stages,legal_sources,source_chunks,stage_citations TO pg_database_owner
            """)
            )
            connection.execute(
                text("GRANT UPDATE ON document_chunks,source_chunks TO pg_database_owner")
            )
            connection.execute(text("GRANT DELETE ON stage_citations TO pg_database_owner"))
    ids = {
        name: uuid4()
        for name in (
            "firm",
            "user",
            "member",
            "project",
            "document",
            "chunk",
            "job",
            "queued",
            "running",
            "new_chunk",
            "stage",
            "source",
            "source_chunk",
            "citation",
            "legacy_citation",
            "second_project",
            "second_stage",
            "firm_source",
            "first_firm_chunk",
            "second_firm_chunk",
            "first_firm_citation",
            "second_firm_citation",
        )
    }
    with tenant_transaction(ids) as connection:
        assert connection.scalar(text("SELECT current_setting('app.firm_id',true)")) == str(
            ids["firm"]
        )
        assert connection.scalar(text("SELECT current_setting('app.user_id',true)")) == str(
            ids["user"]
        )
        for sql in (
            "INSERT INTO firms (id,name) VALUES (:firm,'Audit')",
            "INSERT INTO profiles (id,display_name) VALUES (:user,'Audit')",
            "INSERT INTO firm_members (id,firm_id,profile_id,role) VALUES (:member,:firm,:user,'member')",
            """INSERT INTO projects (id,firm_id,created_by,name,description,jurisdiction,review_status)
               VALUES (:project,:firm,:user,'Project','','','requires_review')""",
            """INSERT INTO documents (id,firm_id,project_id,filename,storage_key,media_type,byte_size,status)
               VALUES (:document,:firm,:project,'old.txt','old','text/plain',3,'pending')""",
            """INSERT INTO document_chunks (id,firm_id,document_id,position,content,embedding,embedding_model)
               VALUES (:chunk,:firm,:document,0,'old','[1,2,3]','legacy-model')""",
            """INSERT INTO generation_jobs (id,firm_id,project_id,status,kind) VALUES
               (:job,:firm,:project,'succeeded','analysis'), (:queued,:firm,:project,'pending','analysis'),
               (:running,:firm,:project,'running','analysis')""",
            """INSERT INTO process_stages(id,firm_id,project_id,title,explanation,position)
               VALUES (:stage,:firm,:project,'Stage','Audit',0)""",
            """INSERT INTO legal_sources(id,firm_id,title,url,jurisdiction)
               VALUES (:source,:firm,'Audit','','')""",
            """INSERT INTO source_chunks(id,firm_id,source_id,position,content,embedding_model)
               VALUES (:source_chunk,:firm,:source,0,'Audit','legacy-model-without-vector')""",
            """INSERT INTO stage_citations(id,firm_id,stage_id,source_chunk_id,excerpt)
               VALUES (:legacy_citation,:firm,:stage,:source_chunk,'Original')""",
        ):
            connection.execute(text(sql), ids)
    migrate("upgrade", "head")
    with tenant_transaction({"firm": uuid4(), "user": uuid4()}) as connection:
        assert not connection.scalar(
            text("SELECT EXISTS(SELECT FROM projects WHERE id=:project)"), ids
        )
    with tenant_transaction(ids) as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
        assert connection.execute(
            text("""
            SELECT project_id, source_scope FROM stage_citations WHERE id=:legacy_citation AND firm_id=:firm
        """),
            ids,
        ).one() == (ids["project"], str(ids["project"]))
        assert (
            connection.scalar(
                text("SELECT role FROM firm_members WHERE firm_id=:firm AND profile_id=:user"), ids
            )
            == "lawyer"
        )
        assert (
            connection.scalar(
                text("SELECT owner_id FROM projects WHERE id=:project AND firm_id=:firm"), ids
            )
            == ids["user"]
        )
        assert (
            connection.scalar(
                text("SELECT processing_status FROM projects WHERE id=:project AND firm_id=:firm"),
                ids,
            )
            == "running"
        )
        assert connection.execute(
            text("SELECT sha256 FROM documents WHERE id=:document AND firm_id=:firm"), ids
        ).one() == (None,)
        assert connection.execute(
            text(
                "SELECT source_filename, embedding IS NULL, legacy_embedding::text FROM document_chunks WHERE id=:chunk AND firm_id=:firm"
            ),
            ids,
        ).one() == ("old.txt", True, "[1,2,3]")
        jobs = dict(
            connection.execute(
                text("SELECT id,status FROM generation_jobs WHERE firm_id=:firm"), ids
            ).all()
        )
        assert jobs == {
            ids["job"]: "completed",
            ids["running"]: "running",
            ids["queued"]: "cancelled",
        }
        assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        table_count = connection.scalar(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        )
        assert table_count >= 16
    with tenant_transaction(ids) as connection:
        connection.execute(
            text("""
            UPDATE source_chunks SET embedding=array_fill(2::real,ARRAY[1536])::vector,
                embedding_model='new-source-model', embedding_provider='audit'
            WHERE id=:source_chunk AND firm_id=:firm
        """),
            ids,
        )
        connection.execute(
            text("""
            UPDATE document_chunks SET embedding=array_fill(1::real,ARRAY[1536])::vector,
                embedding_model='current', embedding_provider='audit' WHERE id=:chunk AND firm_id=:firm
        """),
            ids,
        )
        connection.execute(
            text("""
            INSERT INTO document_chunks (id, firm_id, document_id, position, content, embedding, embedding_model, embedding_provider)
            VALUES (:new_chunk,:firm,:document,1,'new',array_fill(1::real,ARRAY[1536])::vector,'current','audit')
        """),
            ids,
        )
    for target, chunk in (("document_chunk_id", "chunk"), ("source_chunk_id", "source_chunk")):
        with tenant_transaction(ids) as connection:
            connection.execute(
                text(f"""
                INSERT INTO stage_citations(id,firm_id,stage_id,{target},excerpt)
                VALUES (:citation,:firm,:stage,:{chunk},'Audit')
            """),
                ids,
            )
        expect_downgrade_refusal("Step 1 cannot represent existing citation data")
        with tenant_transaction(ids) as connection:
            assert (
                connection.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
            )
            assert (
                connection.scalar(
                    text("""
                SELECT count(*) FROM stage_citations WHERE firm_id=:firm AND stage_id=:stage
            """),
                    ids,
                )
                == 2
            )
            connection.execute(
                text("""
                DELETE FROM stage_citations WHERE firm_id=:firm AND id=:citation
            """),
                ids,
            )
    with tenant_transaction(ids) as connection:
        for sql in (
            """INSERT INTO projects(id,firm_id,created_by,name,description,jurisdiction,review_status)
               VALUES (:second_project,:firm,:user,'Second','','','requires_review')""",
            """INSERT INTO process_stages(id,firm_id,project_id,title,explanation,position)
               VALUES (:second_stage,:firm,:second_project,'Second stage','Audit',0)""",
            """INSERT INTO legal_sources(id,firm_id,title,url,jurisdiction,verification_status)
               VALUES (:firm_source,:firm,'Shared','','','verified')""",
            """INSERT INTO source_chunks(id,firm_id,source_id,position,content) VALUES
               (:first_firm_chunk,:firm,:firm_source,0,'First'),
               (:second_firm_chunk,:firm,:firm_source,1,'Second')""",
            """INSERT INTO stage_citations(id,firm_id,stage_id,source_chunk_id,excerpt) VALUES
               (:first_firm_citation,:firm,:stage,:first_firm_chunk,'First'),
               (:second_firm_citation,:firm,:second_stage,:second_firm_chunk,'Second')""",
        ):
            connection.execute(text(sql), ids)
    expect_downgrade_refusal("verified firm-wide sources cited by multiple projects")
    with tenant_transaction(ids) as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
        assert connection.execute(
            text("""
            SELECT project_id,verification_status FROM legal_sources WHERE firm_id=:firm AND id=:firm_source
        """),
            ids,
        ).one() == (None, "verified")
        assert set(
            connection.execute(
                text("""
            SELECT id,project_id FROM stage_citations WHERE firm_id=:firm AND legal_source_id=:firm_source
        """),
                ids,
            )
        ) == {
            (ids["first_firm_citation"], ids["project"]),
            (ids["second_firm_citation"], ids["second_project"]),
        }
        connection.execute(
            text("DELETE FROM stage_citations WHERE firm_id=:firm AND id=:second_firm_citation"),
            ids,
        )
    migrate("downgrade", step1)
    with tenant_transaction(ids) as connection:
        assert connection.execute(
            text("""
            SELECT embedding=array_fill(2::real,ARRAY[1536])::vector, embedding_model
            FROM source_chunks WHERE id=:source_chunk AND firm_id=:firm
        """),
            ids,
        ).one() == (True, "new-source-model"), "model-only legacy row lost its active embedding"
        assert connection.execute(
            text("""
            SELECT source_chunk_id, excerpt FROM stage_citations WHERE id=:legacy_citation AND firm_id=:firm
        """),
            ids,
        ).one() == (ids["source_chunk"], "Original")
        assert (
            connection.scalar(
                text("SELECT role FROM firm_members WHERE firm_id=:firm AND profile_id=:user"), ids
            )
            == "member"
        )
        assert connection.execute(
            text(
                "SELECT embedding::text, embedding_model FROM document_chunks WHERE id=:chunk AND firm_id=:firm"
            ),
            ids,
        ).one() == ("[1,2,3]", "legacy-model")
        assert connection.execute(
            text("""
            SELECT vector_dims(embedding), embedding_model FROM document_chunks WHERE id=:new_chunk AND firm_id=:firm
        """),
            ids,
        ).one() == (1536, "current")
        assert (
            connection.scalar(
                text("SELECT status FROM generation_jobs WHERE id=:job AND firm_id=:firm"), ids
            )
            == "succeeded"
        )
    migrate("upgrade", "head")
    with tenant_transaction(ids) as connection:
        assert connection.execute(
            text("""
            SELECT project_id,source_chunk_id,excerpt FROM stage_citations
            WHERE firm_id=:firm AND id=:first_firm_citation
        """),
            ids,
        ).one() == (ids["project"], ids["first_firm_chunk"], "First")
    migrate("downgrade", "base")
    migrate("upgrade", "head")
    migrate("check")
    print("Disposable migration audit passed: upgrade, downgrade, and re-upgrade.")
finally:
    audit.dispose()
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{AUDIT_DATABASE}" WITH (FORCE)'))
    admin.dispose()
