"""Verify Alembic in a disposable local database."""

import os
import subprocess
import sys
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
        )
    }
    with audit.begin() as connection:
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
    with audit.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == expected_head
        assert connection.scalar(text("SELECT role FROM firm_members")) == "lawyer"
        assert connection.scalar(text("SELECT owner_id FROM projects")) == ids["user"]
        assert connection.scalar(text("SELECT processing_status FROM projects")) == "running"
        assert connection.scalar(text("SELECT sha256 FROM documents")) is None
        assert connection.execute(
            text(
                "SELECT source_filename, embedding IS NULL, legacy_embedding::text FROM document_chunks"
            )
        ).one() == ("old.txt", True, "[1,2,3]")
        jobs = dict(connection.execute(text("SELECT id,status FROM generation_jobs")).all())
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
    migrate("downgrade", step1)
    with audit.connect() as connection:
        assert connection.scalar(text("SELECT role FROM firm_members")) == "member"
        assert connection.execute(
            text("SELECT embedding::text, embedding_model FROM document_chunks")
        ).one() == ("[1,2,3]", "legacy-model")
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
