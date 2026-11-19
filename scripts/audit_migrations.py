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


@contextmanager
def tenant_transaction(ids):
    with audit.begin() as connection:
        connection.execute(text("""
            SELECT set_config('app.firm_id', :firm, true), set_config('app.user_id', :user, true)
        """), {"firm": str(ids["firm"]), "user": str(ids["user"])})
        yield connection


try:
    migrate("upgrade", step1)
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
            "duplicate",
        )
    }
    with tenant_transaction(ids) as connection:
        assert connection.scalar(text("SELECT current_setting('app.firm_id',true)")) == str(ids["firm"])
        assert connection.scalar(text("SELECT current_setting('app.user_id',true)")) == str(ids["user"])
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
        ):
            connection.execute(text(sql), ids)
    migrate("upgrade", "head")
    with tenant_transaction(ids) as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
        assert connection.scalar(text("SELECT role FROM firm_members WHERE firm_id=:firm AND profile_id=:user"), ids) == "lawyer"
        assert connection.scalar(text("SELECT owner_id FROM projects WHERE id=:project AND firm_id=:firm"), ids) == ids["user"]
        assert connection.scalar(text("SELECT processing_status FROM projects WHERE id=:project AND firm_id=:firm"), ids) == "running"
        assert connection.execute(text("SELECT sha256 FROM documents WHERE id=:document AND firm_id=:firm"), ids).one() == (None,)
        assert connection.execute(
            text(
                "SELECT source_filename, embedding IS NULL, legacy_embedding::text FROM document_chunks WHERE id=:chunk AND firm_id=:firm"
            ), ids
        ).one() == ("old.txt", True, "[1,2,3]")
        jobs = dict(connection.execute(text("SELECT id,status FROM generation_jobs WHERE firm_id=:firm"), ids).all())
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
        connection.execute(text("""
            UPDATE document_chunks SET embedding=array_fill(1::real,ARRAY[1536])::vector,
                embedding_model='current', embedding_provider='audit' WHERE id=:chunk AND firm_id=:firm
        """), ids)
        connection.execute(text("""
            INSERT INTO document_chunks (id, firm_id, document_id, position, content, embedding, embedding_model, embedding_provider)
            VALUES (:new_chunk,:firm,:document,1,'new',array_fill(1::real,ARRAY[1536])::vector,'current','audit')
        """), ids)
        for sql in (
            """INSERT INTO process_stages(id,firm_id,project_id,title,explanation,position)
               VALUES (:stage,:firm,:project,'Stage','Audit',0)""",
            """INSERT INTO legal_sources(id,firm_id,project_id,title,url,jurisdiction)
               VALUES (:source,:firm,:project,'Audit','','')""",
            """INSERT INTO source_chunks(id,firm_id,source_id,position,content)
               VALUES (:source_chunk,:firm,:source,0,'Audit')""",
        ):
            connection.execute(text(sql), ids)
    for target in ("document_chunk_id", "source_chunk_id"):
        with tenant_transaction(ids) as connection:
            if target == "document_chunk_id":
                connection.execute(text("""
                    INSERT INTO stage_citations(id,firm_id,stage_id,document_chunk_id,excerpt)
                    VALUES (:citation,:firm,:stage,:chunk,'Audit')
                """), ids)
                expected_count = 1
            else:
                connection.execute(text("""
                    INSERT INTO stage_citations(id,firm_id,stage_id,source_chunk_id,excerpt) VALUES
                    (:citation,:firm,:stage,:source_chunk,'Audit'),
                    (:duplicate,:firm,:stage,:source_chunk,'Audit')
                """), ids)
                expected_count = 2
        attempt = subprocess.run([*command, "downgrade", step1], env=environment, cwd=REPOSITORY_ROOT,
                                 capture_output=True, text=True)
        assert attempt.returncode != 0 and "Step 1 cannot represent" in attempt.stderr, (
            f"Expected a safe downgrade refusal for {target}"
        )
        with tenant_transaction(ids) as connection:
            assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
            assert connection.scalar(text("""
                SELECT count(*) FROM stage_citations WHERE firm_id=:firm AND stage_id=:stage
            """), ids) == expected_count
            connection.execute(text("""
                DELETE FROM stage_citations WHERE firm_id=:firm AND stage_id=:stage
            """), ids)
    migrate("downgrade", step1)
    with tenant_transaction(ids) as connection:
        assert connection.scalar(text("SELECT role FROM firm_members WHERE firm_id=:firm AND profile_id=:user"), ids) == "member"
        assert connection.execute(
            text("SELECT embedding::text, embedding_model FROM document_chunks WHERE id=:chunk"), ids
        ).one() == ("[1,2,3]", "legacy-model")
        assert connection.execute(text("""
            SELECT vector_dims(embedding), embedding_model FROM document_chunks WHERE id=:new_chunk
        """), ids).one() == (1536, "current")
        assert (
            connection.scalar(text("SELECT status FROM generation_jobs WHERE id=:job"), ids)
            == "succeeded"
        )
    migrate("downgrade", "base")
    migrate("upgrade", "head")
    migrate("check")
    print("Disposable migration audit passed: upgrade, downgrade, and re-upgrade.")
finally:
    audit.dispose()
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{AUDIT_DATABASE}" WITH (FORCE)'))
    admin.dispose()
