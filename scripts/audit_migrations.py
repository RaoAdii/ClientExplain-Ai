"""Verify Alembic in a disposable local database."""

import os
import subprocess
import sys
from pathlib import Path

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
API_ROOT = REPOSITORY_ROOT / "services" / "api"
load_dotenv(REPOSITORY_ROOT / ".env")

AUDIT_DATABASE = "clientexplain_migration_audit"
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is required; run scripts/setup.ps1 first")
admin_url = make_url(database_url).set(database="postgres")
audit_url = make_url(database_url).set(database=AUDIT_DATABASE)
admin = create_engine(admin_url, isolation_level="AUTOCOMMIT")

with admin.connect() as connection:
    connection.execute(text(f'DROP DATABASE IF EXISTS "{AUDIT_DATABASE}" WITH (FORCE)'))
    connection.execute(text(f'CREATE DATABASE "{AUDIT_DATABASE}"'))

environment = os.environ.copy()
environment["DATABASE_URL"] = audit_url.render_as_string(hide_password=False)
command = [sys.executable, "-m", "alembic", "-c", str(API_ROOT / "alembic.ini")]

try:
    subprocess.run([*command, "upgrade", "head"], env=environment, cwd=REPOSITORY_ROOT, check=True)
    audit = create_engine(audit_url)
    with audit.connect() as connection:
        assert connection.scalar(text("SELECT version_num FROM alembic_version")) == "c62fbd003112"
        assert connection.scalar(text("SELECT extversion FROM pg_extension WHERE extname='vector'"))
        table_count = connection.scalar(
            text("SELECT count(*) FROM information_schema.tables WHERE table_schema='public'")
        )
        assert table_count >= 16
    audit.dispose()
    subprocess.run(
        [*command, "downgrade", "base"], env=environment, cwd=REPOSITORY_ROOT, check=True
    )
    subprocess.run([*command, "upgrade", "head"], env=environment, cwd=REPOSITORY_ROOT, check=True)
    print("Disposable migration audit passed: upgrade, downgrade, and re-upgrade.")
finally:
    with admin.connect() as connection:
        connection.execute(text(f'DROP DATABASE IF EXISTS "{AUDIT_DATABASE}" WITH (FORCE)'))
    admin.dispose()
