"""Tenant policies and database-maintained update timestamps."""

from alembic import op

revision = "c62fbd003112"
down_revision = "b83406a26f40"
branch_labels = None
depends_on = None

TENANT_TABLES = (
    "projects",
    "documents",
    "document_chunks",
    "legal_sources",
    "source_chunks",
    "process_stages",
    "stage_citations",
    "generated_assets",
    "generation_jobs",
    "project_versions",
    "exports",
    "audit_events",
)
TABLES = ("profiles", "firms", "firm_members", *TENANT_TABLES)


def upgrade():
    op.execute("""CREATE FUNCTION touch_updated_at() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN NEW.updated_at = now(); RETURN NEW; END; $$""")
    firm = "NULLIF(current_setting('app.firm_id', true), '')::uuid"
    user = "NULLIF(current_setting('app.user_id', true), '')::uuid"
    for table in TABLES:
        op.execute(
            f"CREATE TRIGGER update_timestamp BEFORE UPDATE ON {table} FOR EACH ROW EXECUTE FUNCTION touch_updated_at()"
        )
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
    for table in TENANT_TABLES:
        op.execute(
            f"CREATE POLICY tenant_access ON {table} USING (firm_id = {firm}) WITH CHECK (firm_id = {firm})"
        )
    op.execute(
        f"CREATE POLICY profile_self ON profiles USING (id = {user}) WITH CHECK (id = {user})"
    )
    op.execute(f"CREATE POLICY firm_access ON firms USING (id = {firm}) WITH CHECK (id = {firm})")
    op.execute(
        f"CREATE POLICY membership_read ON firm_members FOR SELECT USING (profile_id = {user})"
    )
    op.execute(
        f"CREATE POLICY membership_create ON firm_members FOR INSERT WITH CHECK (profile_id = {user} AND firm_id = {firm})"
    )


def downgrade():
    for table in TABLES:
        op.execute(f"DROP TRIGGER update_timestamp ON {table}")
        op.execute(f"ALTER TABLE {table} DISABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} NO FORCE ROW LEVEL SECURITY")
    for table in TENANT_TABLES:
        op.execute(f"DROP POLICY tenant_access ON {table}")
    op.execute("DROP POLICY profile_self ON profiles")
    op.execute("DROP POLICY firm_access ON firms")
    op.execute("DROP POLICY membership_read ON firm_members")
    op.execute("DROP POLICY membership_create ON firm_members")
    op.execute("DROP FUNCTION touch_updated_at()")
