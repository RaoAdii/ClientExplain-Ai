"""Expand the tenant workflow without assigning unverified provenance to Step 1 data."""

from alembic import op

revision = "a27d9c4e8b11"
down_revision = "c62fbd003112"
branch_labels = None
depends_on = None

CHUNKS = ("document_chunks", "source_chunks")
BACKFILLED = (
    "firm_members",
    "projects",
    "documents",
    "document_chunks",
    "generation_jobs",
    "stage_citations",
    "source_chunks",
    "legal_sources",
    "process_stages",
)


def set_force_rls(enabled):
    # A table owner can migrate under FORCE RLS without requiring BYPASSRLS.
    # ALTER holds ACCESS EXCLUSIVE until this migration transaction commits.
    for table in BACKFILLED:
        op.execute(f"ALTER TABLE {table} {'FORCE' if enabled else 'NO FORCE'} ROW LEVEL SECURITY")


def install_citation_provenance():
    # Step 1 stored no project or verification state on a legal source.
    # Recover the narrowest scope supported by its existing references.
    op.execute("""DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM stage_citations c
            JOIN source_chunks ch ON (ch.id,ch.firm_id)=(c.source_chunk_id,c.firm_id)
            JOIN legal_sources s ON (s.id,s.firm_id)=(ch.source_id,ch.firm_id)
            JOIN process_stages st ON (st.id,st.firm_id)=(c.stage_id,c.firm_id)
            WHERE s.project_id IS NULL AND s.verification_status='unverified'
            GROUP BY s.id HAVING count(DISTINCT st.project_id)>1
        ) THEN
            RAISE EXCEPTION 'Legacy unverified sources have citations in multiple projects. Resolve source ownership before upgrading.';
        END IF;
    END $$""")
    op.execute("""
        UPDATE legal_sources s SET project_id=st.project_id FROM stage_citations c
        JOIN source_chunks ch ON (ch.id,ch.firm_id)=(c.source_chunk_id,c.firm_id)
        JOIN process_stages st ON (st.id,st.firm_id)=(c.stage_id,c.firm_id)
        WHERE (s.id,s.firm_id)=(ch.source_id,ch.firm_id)
          AND s.project_id IS NULL AND s.verification_status='unverified'
    """)
    op.execute("""ALTER TABLE legal_sources ADD citation_scope text GENERATED ALWAYS AS
                  (coalesce(project_id::text,verification_status)) STORED NOT NULL,
                  ADD CONSTRAINT uq_legal_sources_citation_scope UNIQUE (id,citation_scope,firm_id)""")
    op.execute(
        "ALTER TABLE document_chunks ADD CONSTRAINT uq_document_chunks_parent UNIQUE (id,document_id,firm_id)"
    )
    op.execute(
        "ALTER TABLE source_chunks ADD CONSTRAINT uq_source_chunks_parent UNIQUE (id,source_id,firm_id)"
    )
    op.execute(
        "ALTER TABLE process_stages ADD CONSTRAINT uq_process_stages_project UNIQUE (id,project_id,firm_id)"
    )
    op.execute("""
        ALTER TABLE stage_citations ADD project_id uuid, ADD document_id uuid, ADD legal_source_id uuid, ADD source_scope text,
        ADD FOREIGN KEY (stage_id,project_id,firm_id) REFERENCES process_stages (id,project_id,firm_id) ON DELETE CASCADE,
        ADD FOREIGN KEY (document_chunk_id,document_id,firm_id) REFERENCES document_chunks (id,document_id,firm_id) ON DELETE CASCADE,
        ADD FOREIGN KEY (document_id,project_id,firm_id) REFERENCES documents (id,project_id,firm_id) ON DELETE CASCADE,
        ADD FOREIGN KEY (source_chunk_id,legal_source_id,firm_id) REFERENCES source_chunks (id,source_id,firm_id) ON DELETE CASCADE,
        ADD FOREIGN KEY (legal_source_id,source_scope,firm_id) REFERENCES legal_sources (id,citation_scope,firm_id) ON DELETE CASCADE
    """)
    op.execute("""CREATE FUNCTION derive_citation_ancestry() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            SELECT project_id INTO NEW.project_id FROM process_stages
             WHERE (id,firm_id)=(NEW.stage_id,NEW.firm_id);
            SELECT document_id INTO NEW.document_id FROM document_chunks
             WHERE (id,firm_id)=(NEW.document_chunk_id,NEW.firm_id);
            SELECT s.id,s.citation_scope INTO NEW.legal_source_id,NEW.source_scope
             FROM source_chunks ch JOIN legal_sources s ON (s.id,s.firm_id)=(ch.source_id,ch.firm_id)
             WHERE (ch.id,ch.firm_id)=(NEW.source_chunk_id,NEW.firm_id);
            RETURN NEW;
        END; $$""")
    op.execute("""CREATE TRIGGER derive_ancestry BEFORE INSERT OR UPDATE ON stage_citations
                  FOR EACH ROW EXECUTE FUNCTION derive_citation_ancestry()""")
    op.execute("UPDATE stage_citations SET project_id=NULL")
    op.execute("""ALTER TABLE stage_citations ALTER project_id SET NOT NULL,
        ADD CONSTRAINT ck_stage_citations_document_parent CHECK (document_chunk_id IS NULL OR document_id IS NOT NULL),
        ADD CONSTRAINT ck_stage_citations_source_scope CHECK (source_chunk_id IS NULL OR
            (legal_source_id IS NOT NULL AND source_scope IS NOT NULL AND source_scope IN ('verified', project_id::text)))
    """)


def upgrade():
    set_force_rls(False)
    op.execute("ALTER TABLE firm_members DROP CONSTRAINT firm_members_role_check")
    op.execute("UPDATE firm_members SET role='lawyer' WHERE role='member'")
    op.execute("""
        ALTER TABLE firm_members ALTER role SET DEFAULT 'lawyer',
        ADD CONSTRAINT ck_firm_members_role CHECK (role IN ('owner','admin','lawyer','reviewer'))
    """)
    op.execute("""
        ALTER TABLE projects
        ADD owner_id uuid REFERENCES profiles (id),
        ADD legal_area varchar(120) NOT NULL DEFAULT '',
        ADD language varchar(60) NOT NULL DEFAULT '',
        ADD target_audience varchar(120) NOT NULL DEFAULT '',
        ADD complexity varchar(40) NOT NULL DEFAULT 'unspecified',
        ADD workflow_status varchar(30) NOT NULL DEFAULT 'draft'
            CONSTRAINT ck_projects_workflow_status CHECK (workflow_status IN ('draft','active','archived')),
        ADD processing_status varchar(30) NOT NULL DEFAULT 'idle'
            CONSTRAINT ck_projects_processing_status CHECK (processing_status IN ('idle','queued','running','completed','failed','cancelled'))
    """)
    op.execute("UPDATE projects SET owner_id=created_by")
    op.execute("ALTER TABLE projects ALTER owner_id SET NOT NULL")
    op.execute("""CREATE FUNCTION default_project_owner() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN NEW.owner_id = coalesce(NEW.owner_id, NEW.created_by); RETURN NEW; END; $$""")
    op.execute("""CREATE TRIGGER default_owner BEFORE INSERT ON projects
                  FOR EACH ROW EXECUTE FUNCTION default_project_owner()""")
    op.execute(
        "CREATE INDEX ix_projects_workflow ON projects (firm_id, workflow_status, updated_at)"
    )
    op.execute("CREATE INDEX ix_projects_review ON projects (firm_id, review_status, updated_at)")
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_projects_name_search ON projects USING gin (name gin_trgm_ops)")

    op.execute("""
        ALTER TABLE documents ALTER status SET DEFAULT 'pending',
        ADD sha256 varchar(64) CONSTRAINT ck_documents_sha256 CHECK (sha256 ~ '^[0-9a-f]{64}$'),
        ADD metadata json NOT NULL DEFAULT '{}',
        ADD page_count integer CONSTRAINT ck_documents_page_count CHECK (page_count >= 0),
        ADD parsing_error varchar(300), ADD ocr_required boolean NOT NULL DEFAULT false,
        ADD deleted_at timestamptz, ADD deleted_by uuid REFERENCES profiles (id),
        ADD CONSTRAINT uq_documents_project_sha256 UNIQUE (firm_id, project_id, sha256),
        ADD CONSTRAINT uq_documents_project_identity UNIQUE (id, project_id, firm_id)
    """)
    # The old database has no bytes from which to derive a truthful SHA-256.
    op.execute("""CREATE FUNCTION require_document_sha256() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN
            IF NEW.sha256 IS NULL AND (TG_OP = 'INSERT' OR OLD.sha256 IS NOT NULL) THEN
                RAISE EXCEPTION 'Document SHA-256 is required' USING ERRCODE='23502';
            END IF;
            RETURN NEW;
        END; $$""")
    op.execute("""CREATE TRIGGER require_sha256 BEFORE INSERT OR UPDATE OF sha256 ON documents
                  FOR EACH ROW EXECUTE FUNCTION require_document_sha256()""")

    for table in CHUNKS:
        # Retain old vectors outside the retrieval index. The Step 1 schema
        # admitted arbitrary dimensions and recorded no provider identity.
        op.execute(f"ALTER TABLE {table} RENAME embedding TO legacy_embedding")
        op.execute(f"ALTER TABLE {table} RENAME embedding_model TO legacy_embedding_model")
        op.execute(f"""
            ALTER TABLE {table} ADD embedding vector(1536), ADD embedding_model varchar(120),
            ADD embedding_provider varchar(60), ADD heading text,
            ADD page_number integer CONSTRAINT ck_{table}_page_number CHECK (page_number > 0),
            ADD metadata json NOT NULL DEFAULT '{{}}',
            ADD CONSTRAINT ck_{table}_embedding_provenance CHECK (
                embedding IS NULL OR (embedding_model IS NOT NULL AND embedding_provider IS NOT NULL))
        """)
        op.execute(
            f"CREATE INDEX ix_{table}_embedding ON {table} USING hnsw (embedding vector_cosine_ops)"
        )
    op.execute("""
        ALTER TABLE document_chunks ADD source_filename varchar(255),
        ADD char_start integer, ADD char_end integer, ADD token_start integer, ADD token_end integer,
        ADD CONSTRAINT ck_document_chunks_char_offsets CHECK (char_start >= 0 AND char_end >= char_start),
        ADD CONSTRAINT ck_document_chunks_token_offsets CHECK (token_start >= 0 AND token_end >= token_start),
        ADD CONSTRAINT uq_document_chunks_identity UNIQUE (id, firm_id)
    """)
    op.execute("""UPDATE document_chunks c SET source_filename=d.filename FROM documents d
                  WHERE (c.document_id, c.firm_id) = (d.id, d.firm_id)""")

    op.execute("""
        ALTER TABLE legal_sources
        ADD source_type varchar(40) NOT NULL DEFAULT 'unspecified', ADD citation_reference text,
        ADD effective_date date, ADD repeal_date date,
        ADD verification_status varchar(30) NOT NULL DEFAULT 'unverified'
            CONSTRAINT ck_legal_sources_verification CHECK (verification_status IN ('verified','unverified')),
        ADD last_verified_at timestamptz, ADD metadata json NOT NULL DEFAULT '{}',
        ADD project_id uuid, ADD document_id uuid,
        ADD FOREIGN KEY (project_id, firm_id) REFERENCES projects (id, firm_id) ON DELETE CASCADE,
        ADD FOREIGN KEY (document_id, project_id, firm_id) REFERENCES documents (id, project_id, firm_id) ON DELETE CASCADE,
        ADD CONSTRAINT ck_legal_sources_document_project CHECK (document_id IS NULL OR project_id IS NOT NULL),
        ADD CONSTRAINT ck_legal_sources_dates CHECK (repeal_date >= effective_date)
    """)
    op.execute(
        "CREATE INDEX ix_legal_sources_retrieval ON legal_sources (firm_id, project_id, jurisdiction, verification_status)"
    )
    op.execute("""
        ALTER TABLE process_stages ADD responsible_party text,
        ADD required_documents json NOT NULL DEFAULT '[]', ADD estimated_duration text,
        ADD source_backed boolean NOT NULL DEFAULT false,
        ADD general_explanation boolean NOT NULL DEFAULT true,
        ADD limitations json NOT NULL DEFAULT '[]', ADD visual_prompt text,
        ADD verification_status varchar(30) NOT NULL DEFAULT 'unverified'
            CONSTRAINT ck_process_stages_verification CHECK (verification_status IN ('supported','unverified','unsupported'))
    """)
    op.execute("""
        ALTER TABLE stage_citations ALTER source_chunk_id DROP NOT NULL,
        DROP CONSTRAINT stage_citations_stage_id_source_chunk_id_key,
        DROP CONSTRAINT stage_citations_source_chunk_id_firm_id_fkey,
        ADD document_chunk_id uuid, ADD claim_text text NOT NULL DEFAULT '',
        ADD validation_status varchar(30) NOT NULL DEFAULT 'unverified'
            CONSTRAINT ck_stage_citations_validation CHECK (validation_status IN ('supported','unverified','unsupported')),
        ADD FOREIGN KEY (source_chunk_id, firm_id) REFERENCES source_chunks (id, firm_id) ON DELETE CASCADE,
        ADD FOREIGN KEY (document_chunk_id, firm_id) REFERENCES document_chunks (id, firm_id) ON DELETE CASCADE,
        ADD CONSTRAINT ck_stage_citations_one_target CHECK (num_nonnulls(source_chunk_id, document_chunk_id) = 1)
    """)
    op.execute(
        "CREATE INDEX ix_stage_citations_document_chunk_id ON stage_citations (document_chunk_id)"
    )
    install_citation_provenance()

    op.execute("""
        ALTER TABLE generation_jobs DROP CONSTRAINT generation_jobs_status_check,
        ALTER status SET DEFAULT 'queued', ADD error_message varchar(300), ADD current_stage varchar(80),
        ADD progress integer NOT NULL DEFAULT 0 CONSTRAINT ck_generation_jobs_progress CHECK (progress BETWEEN 0 AND 100),
        ADD retry_count integer NOT NULL DEFAULT 0 CONSTRAINT ck_generation_jobs_retry_count CHECK (retry_count >= 0),
        ADD request_hash varchar(64), ADD idempotency_key varchar(200),
        ADD request_metadata json NOT NULL DEFAULT '{}', ADD started_at timestamptz, ADD finished_at timestamptz,
        ADD CONSTRAINT uq_generation_jobs_project_identity UNIQUE (id, project_id, firm_id),
        ADD CONSTRAINT uq_generation_jobs_submission UNIQUE (firm_id, project_id, kind, idempotency_key)
    """)
    op.execute("UPDATE generation_jobs SET status='queued' WHERE status='pending'")
    op.execute(
        "UPDATE generation_jobs SET status='completed', progress=100 WHERE status='succeeded'"
    )
    # Step 1 permitted overlapping jobs. Prefer an already-running job,
    # then the oldest submission, and retain a terminal record for each duplicate.
    op.execute("""
        WITH ranked AS (
            SELECT id, row_number() OVER (PARTITION BY firm_id, project_id
                ORDER BY (status='running') DESC, created_at, id) AS position
            FROM generation_jobs WHERE kind='analysis' AND status IN ('queued','running')
        )
        UPDATE generation_jobs j SET status='cancelled', error_code='superseded_by_migration',
            finished_at=now() FROM ranked r WHERE j.id=r.id AND r.position > 1
    """)
    op.execute("""
        WITH current_analysis AS (
            SELECT DISTINCT ON (firm_id, project_id) firm_id, project_id, status
            FROM generation_jobs WHERE kind='analysis'
            ORDER BY firm_id, project_id, (status IN ('running','queued')) DESC, created_at DESC, id
        )
        UPDATE projects p SET processing_status=j.status FROM current_analysis j
        WHERE (p.firm_id, p.id)=(j.firm_id, j.project_id)
    """)
    op.execute("""ALTER TABLE generation_jobs ADD CONSTRAINT ck_generation_jobs_status
                  CHECK (status IN ('queued','running','completed','failed','cancelled'))""")
    op.execute("""CREATE UNIQUE INDEX uq_generation_jobs_active_analysis ON generation_jobs (firm_id, project_id)
                  WHERE kind='analysis' AND status IN ('queued','running')""")
    op.execute(
        "CREATE INDEX ix_generation_jobs_project_created ON generation_jobs (firm_id, project_id, created_at)"
    )
    op.execute("""
        ALTER TABLE project_versions ADD generation_job_id uuid UNIQUE,
        ADD FOREIGN KEY (generation_job_id, project_id, firm_id) REFERENCES generation_jobs (id, project_id, firm_id)
    """)
    op.execute("""CREATE FUNCTION reject_version_update() RETURNS trigger LANGUAGE plpgsql AS $$
        BEGIN RAISE EXCEPTION 'Project versions are immutable' USING ERRCODE='23514'; END; $$""")
    op.execute("""CREATE TRIGGER immutable_version BEFORE UPDATE ON project_versions
                  FOR EACH ROW EXECUTE FUNCTION reject_version_update()""")
    set_force_rls(True)


def downgrade():
    # Lock the backfilled tables and let the owner inspect every firm before
    # changing the schema. A refusal rolls back the temporary FORCE settings.
    set_force_rls(False)
    op.execute("""DO $$ BEGIN
        IF EXISTS (
            SELECT 1 FROM stage_citations WHERE source_scope='verified'
            GROUP BY firm_id,legal_source_id HAVING count(DISTINCT project_id)>1
        ) THEN
            RAISE EXCEPTION 'Step 1 cannot represent verified firm-wide sources cited by multiple projects. Archive or explicitly resolve these cross-project citation associations before downgrading.';
        END IF;
        ALTER TABLE stage_citations ALTER source_chunk_id SET NOT NULL,
            ADD UNIQUE (stage_id,source_chunk_id),
            ADD CHECK (claim_text='' AND validation_status='unverified');
    EXCEPTION WHEN not_null_violation OR unique_violation OR check_violation THEN
        RAISE EXCEPTION 'Step 1 cannot represent existing citation data. Archive and explicitly resolve these citations before downgrading.';
    END $$""")
    op.execute("DROP TRIGGER derive_ancestry ON stage_citations")
    op.execute("DROP FUNCTION derive_citation_ancestry()")
    op.execute(
        "ALTER TABLE stage_citations DROP project_id, DROP document_id, DROP legal_source_id, DROP source_scope"
    )
    op.execute("ALTER TABLE legal_sources DROP citation_scope")
    op.execute("ALTER TABLE process_stages DROP CONSTRAINT uq_process_stages_project")
    op.execute("ALTER TABLE document_chunks DROP CONSTRAINT uq_document_chunks_parent")
    op.execute("ALTER TABLE source_chunks DROP CONSTRAINT uq_source_chunks_parent")
    op.execute("DROP TRIGGER immutable_version ON project_versions")
    op.execute("DROP FUNCTION reject_version_update()")
    op.execute("ALTER TABLE project_versions DROP generation_job_id")
    op.execute("DROP INDEX uq_generation_jobs_active_analysis")
    op.execute("DROP INDEX ix_generation_jobs_project_created")
    op.execute("""
        ALTER TABLE generation_jobs DROP CONSTRAINT ck_generation_jobs_status,
        DROP CONSTRAINT uq_generation_jobs_project_identity, ALTER status DROP DEFAULT,
        DROP error_message, DROP current_stage, DROP progress, DROP retry_count,
        DROP request_hash, DROP idempotency_key, DROP request_metadata, DROP started_at, DROP finished_at
    """)
    op.execute("UPDATE generation_jobs SET status='pending' WHERE status='queued'")
    op.execute("UPDATE generation_jobs SET status='succeeded' WHERE status='completed'")
    op.execute("""ALTER TABLE generation_jobs ADD CONSTRAINT generation_jobs_status_check
                  CHECK (status IN ('pending','running','succeeded','failed','cancelled'))""")

    op.execute("""
        ALTER TABLE stage_citations DROP CONSTRAINT stage_citations_source_chunk_id_firm_id_fkey,
        DROP document_chunk_id, DROP claim_text, DROP validation_status,
        ADD FOREIGN KEY (source_chunk_id, firm_id) REFERENCES source_chunks (id, firm_id)
    """)
    op.execute("""
        ALTER TABLE process_stages DROP responsible_party, DROP required_documents, DROP estimated_duration,
        DROP source_backed, DROP general_explanation, DROP limitations, DROP visual_prompt, DROP verification_status
    """)
    op.execute("""
        ALTER TABLE legal_sources DROP source_type, DROP citation_reference, DROP effective_date, DROP repeal_date,
        DROP verification_status, DROP last_verified_at, DROP metadata, DROP project_id, DROP document_id
    """)
    op.execute("""ALTER TABLE document_chunks DROP source_filename, DROP char_start, DROP char_end,
                  DROP token_start, DROP token_end, DROP CONSTRAINT uq_document_chunks_identity""")
    for table in CHUNKS:
        op.execute(f"""UPDATE {table} SET legacy_embedding=embedding, legacy_embedding_model=embedding_model
                      WHERE legacy_embedding IS NULL AND embedding IS NOT NULL""")
        op.execute(f"""ALTER TABLE {table} DROP embedding, DROP embedding_model, DROP embedding_provider,
                      DROP heading, DROP page_number, DROP metadata""")
        op.execute(f"ALTER TABLE {table} RENAME legacy_embedding TO embedding")
        op.execute(f"ALTER TABLE {table} RENAME legacy_embedding_model TO embedding_model")
    op.execute("DROP TRIGGER require_sha256 ON documents")
    op.execute("DROP FUNCTION require_document_sha256()")
    op.execute("""
        ALTER TABLE documents ALTER status DROP DEFAULT, DROP sha256, DROP metadata, DROP page_count,
        DROP parsing_error, DROP ocr_required, DROP deleted_at, DROP deleted_by, DROP CONSTRAINT uq_documents_project_identity
    """)
    op.execute("DROP INDEX ix_projects_name_search")
    # The database may already have used pg_trgm before this revision.
    op.execute("DROP INDEX ix_projects_review")
    op.execute("DROP TRIGGER default_owner ON projects")
    op.execute("DROP FUNCTION default_project_owner()")
    op.execute("""ALTER TABLE projects DROP owner_id, DROP legal_area, DROP language, DROP target_audience,
                  DROP complexity, DROP workflow_status, DROP processing_status""")
    op.execute(
        "ALTER TABLE firm_members DROP CONSTRAINT ck_firm_members_role, ALTER role DROP DEFAULT"
    )
    op.execute("UPDATE firm_members SET role='member' WHERE role <> 'owner'")
    op.execute(
        "ALTER TABLE firm_members ADD CONSTRAINT firm_members_role_check CHECK (role IN ('owner','member'))"
    )
    set_force_rls(True)
