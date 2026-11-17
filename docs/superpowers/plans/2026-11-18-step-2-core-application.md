# ClientExplain AI Step 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the authenticated, tenant-safe project, private-document, background-processing, RAG and structured legal-analysis workflow defined for Step 2 without fabricating provider results.

**Architecture:** Extend the existing Next.js BFF and FastAPI modular monolith, keeping PostgreSQL as durable state and Redis/Celery as the asynchronous execution path. Local parsing and private filesystem storage work without cloud credentials; OpenAI Responses/Embeddings and Supabase private Storage are real adapters gated by configuration and explicit external-processing approval.

**Tech Stack:** Next.js 16 App Router, React 19, TypeScript, TanStack Query, React Hook Form, Zod, FastAPI, Pydantic 2, SQLAlchemy 2, Alembic, PostgreSQL 16/pgvector, Redis, Celery, OpenAI Python SDK, PyMuPDF, python-docx, Supabase Storage REST, Pytest, Vitest and Playwright.

**Spec:** `docs/superpowers/specs/2026-11-18-step-2-core-application-design.md`

## Global Constraints

- Preserve the committed Step 1 architecture, naming conventions, responsive design and all passing tests.
- Python remains 3.11; Node remains 22.23.5; long-running parsing, embedding and analysis execute only in Celery.
- No document content leaves local storage unless `AI_EXTERNAL_PROCESSING_ALLOWED=true` and an authorized user explicitly selects that document for analysis.
- Runtime has no fake AI provider. Controlled provider doubles are test-only; missing credentials return explicit configuration errors.
- Every generated explanation has `review_required=true`; uploaded documents are `user_document/unverified`, never official legal authority.
- No secret, token, password, prompt, document body or complete client text may appear in logs or API errors.
- Firm IDs and roles come only from verified membership; cross-firm resources return 404.
- No purple gradients, pill buttons, emoji, fake metrics, fake activity, generic AI imagery or Step 3 image/diagram/export functionality.
- Use current OpenAI Responses structured parsing (`client.responses.parse(..., text_format=LegalProcess)`) and embeddings. The selected initial embedding model is `text-embedding-3-small` at its documented default 1536 dimensions; validate returned dimensions before persistence. Official references: `https://developers.openai.com/api/docs/guides/structured-outputs` and `https://developers.openai.com/api/docs/guides/embeddings`.
- Preserve the user/toolchain-owned `apps/web/next-env.d.ts` change unless a verified Next.js build regenerates it as required.

## Review Focus

1. A file whose extension/MIME claims PDF but whose signature is not PDF must be rejected before storage or parsing; covered in Task 5 upload admission tests.
2. An analysis request selecting an OCR-required, failed or cross-firm document must return 409/404 and must never silently omit it; covered in Task 9 API tests.
3. A slower or duplicate analysis request must not overwrite a newer/current result; covered by the active-job uniqueness and idempotency tests in Tasks 4 and 8.
4. Deleting a project while a worker is running must not recreate rows or retain private files/snapshots; covered by Task 8 cancellation/deletion tests.
5. Model output that names an unknown chunk, alters jurisdiction, omits citations for a source-backed claim or sets `review_required=false` must fail validation and publish no partial stages; covered in Tasks 7 and 8.

---

## File and module map

- `services/api/app/models/entities.py`: canonical SQLAlchemy entities and additive Step 2 fields/constraints.
- `services/api/app/core/config.py`: validated upload, storage, provider, model, dimension, retrieval and rate-limit settings.
- `services/api/app/core/auth.py`, `core/permissions.py`: verified principal/membership resolution and role policy.
- `services/api/app/schemas/{auth,projects,documents,jobs,analysis,sources}.py`: bounded public contracts.
- `services/api/app/repositories/{projects,documents,jobs,analysis,sources}.py`: tenant-filtered persistence only.
- `services/api/app/services/{projects,documents,jobs,analysis,rag,citations,activity}.py`: domain rules and transactions.
- `services/api/app/integrations/{storage,openai_provider}.py`: local/Supabase private storage and OpenAI adapters.
- `services/api/app/api/{auth,projects,documents,analysis}.py`: route modules aggregated by `api/routes.py`.
- `services/worker/tasks/{documents,analysis}.py`, `pipelines/{documents,chunking,analysis}.py`: idempotent Celery orchestration and pure pipelines.
- `apps/web/src/app/{forgot-password,reset-password,auth/callback,...}`: account flows and Step 2 routes.
- `apps/web/src/components/{project-workspace,document-upload,document-list,analysis-form,job-progress,process-results,citation-viewer}.tsx`: focused workspace UI.
- `apps/web/src/services/{api,uploads}.ts`, `types/{project,document,analysis}.ts`, `lib/validation.ts`: browser contracts and validation.

### Task 1: Lock Step 2 dependencies and configuration

**Files:**
- Modify: `services/api/requirements.in`
- Modify: `services/api/requirements.lock`
- Modify: `apps/web/package.json`
- Modify: `package-lock.json`
- Modify: `apps/web/vitest.config.ts`
- Create: `apps/web/vitest.setup.ts`
- Modify: `.env.example`
- Modify: `services/api/app/core/config.py`
- Modify: `scripts/setup.ps1`
- Modify: `scripts/configure.py`
- Test: `services/api/tests/test_config.py`

**Interfaces:**
- Produces: `Settings.storage_backend`, `private_storage_root`, `supabase_storage_bucket`, server-only `supabase_service_role_key`, `max_upload_bytes`, `openai_api_key`, `openai_analysis_model`, `embedding_model`, `embedding_dimensions`, `ai_external_processing_allowed`, `retrieval_limit`, `retrieval_threshold`, and rate-limit values.
- Consumes: existing `Settings` authentication/database fields.

- [ ] **Step 1: Add failing configuration tests**

Add `test_external_ai_requires_key_model_and_embedding_pair`, `test_embedding_dimension_is_1536_for_initial_model`, `test_production_rejects_local_storage`, and `test_upload_limits_are_bounded`. Assert external AI cannot enable without a key/model, the selected model/dimension pair is exact, and local storage is development/test only.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_config.py -q`

Expected: FAIL because Step 2 settings do not exist.

- [ ] **Step 3: Add and lock dependencies**

Add bounded versions for `openai`, `PyMuPDF`, `python-docx`, `python-multipart`, and any OpenAI-required `httpx` dependency while retaining `httpx2` for Starlette compatibility. Regenerate `requirements.lock` under Python 3.11 and document why both HTTP packages are intentional.

Add bounded frontend test dependencies `@testing-library/react`, `@testing-library/jest-dom`, `@testing-library/user-event` and `jsdom`; configure `vitest.config.ts` for `.test.ts` and `.test.tsx` with jsdom plus `vitest.setup.ts`, without changing production runtime dependencies.

- [ ] **Step 4: Implement validated settings and safe local defaults**

Keep `AI_EXTERNAL_PROCESSING_ALLOWED=false`, `STORAGE_BACKEND=local`, `MAX_UPLOAD_BYTES=26214400`, `EMBEDDING_MODEL=text-embedding-3-small`, and `EMBEDDING_DIMENSIONS=1536`. Require an explicit analysis model only when external processing is enabled. Generate an ignored `PRIVATE_STORAGE_ROOT` path without creating public files.

- [ ] **Step 5: Run configuration and dependency checks**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_config.py -q; .\.venv\Scripts\python.exe -m pip check`

Expected: all focused tests pass; no broken requirements.

- [ ] **Step 6: Commit**

```powershell
git add services/api/requirements.in services/api/requirements.lock services/api/app/core/config.py services/api/tests/test_config.py apps/web/package.json apps/web/vitest.config.ts apps/web/vitest.setup.ts package-lock.json .env.example scripts/setup.ps1 scripts/configure.py
git commit -m "build: configure Step 2 providers and parsing"
```

### Task 2: Evolve the tenant data model and migrations

**Files:**
- Modify: `services/api/app/models/entities.py`
- Create: `services/api/migrations/versions/a27d9c4e8b11_step_2_core_workflow.py`
- Modify: `services/api/app/api/routes.py` (readiness revision)
- Modify: `scripts/audit_migrations.py` (derive expected head instead of a fixed Step 1 revision)
- Test: `services/api/tests/test_step2_database.py`
- Test: `services/api/tests/test_database.py`

**Interfaces:**
- Produces: expanded `FirmMember`, `Project`, `Document`, `DocumentChunk`, `LegalSource`, `SourceChunk`, `ProcessStage`, `StageCitation`, `GenerationJob`, and `ProjectVersion` mappings.
- Produces job statuses exactly `queued|running|completed|failed|cancelled` and role values exactly `owner|admin|lawyer|reviewer`.

- [ ] **Step 1: Write failing schema tests**

Create tests asserting all new columns/defaults/checks, composite tenant foreign keys, document SHA uniqueness within a project, exactly-one citation target, 1536-dimensional vectors, partial uniqueness for one active analysis job, RLS coverage and database-maintained timestamps.

- [ ] **Step 2: Run database tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_step2_database.py -q`

Expected: FAIL on missing fields/constraints.

- [ ] **Step 3: Expand SQLAlchemy mappings**

Use nullable transitional columns only where the migration must backfill existing Step 1 rows. Include stage `visual_prompt` as persisted Step 3 preparation without generating images. Store process-level metadata (`process_name`, summary, applicability date, audience, complexity, limitations, missing information and mandatory review flag) inside the immutable current `ProjectVersion.snapshot`; store analysis request metadata without raw document text. Keep composite `(id, firm_id)` uniqueness for every cross-tenant child relation.

- [ ] **Step 4: Create the additive migration**

Map `member` to `lawyer`, `pending` to `queued`, and `succeeded` to `completed`; backfill project fields with truthful defaults; add indexes and updated RLS policies/triggers. Do not reference Supabase schemas.

- [ ] **Step 5: Verify upgrade, downgrade, re-upgrade and drift**

Run: `.\.venv\Scripts\python.exe scripts/audit_migrations.py; .\.venv\Scripts\alembic.exe -c services/api/alembic.ini upgrade head; .\.venv\Scripts\alembic.exe -c services/api/alembic.ini check`

Expected: disposable round trip passes; database reaches `a27d9c4e8b11`; no model drift.

- [ ] **Step 6: Commit**

```powershell
git add services/api/app/models/entities.py services/api/migrations services/api/tests/test_step2_database.py services/api/tests/test_database.py services/api/app/api/routes.py scripts/audit_migrations.py
git commit -m "feat: add Step 2 relational workflow"
```

### Task 3: Enforce membership roles and extend project management

**Files:**
- Create: `services/api/app/core/permissions.py`
- Create: `services/api/app/schemas/auth.py`
- Modify: `services/api/app/schemas/projects.py`
- Create: `services/api/app/api/auth.py`
- Create: `services/api/app/api/projects.py`
- Modify: `services/api/app/api/routes.py`
- Modify: `services/api/app/core/auth.py`
- Modify: `services/api/app/repositories/projects.py`
- Modify: `services/api/app/services/projects.py`
- Create: `services/api/app/services/activity.py`
- Test: `services/api/tests/test_authz.py`
- Test: `services/api/tests/test_projects_step2.py`

**Interfaces:**
- Produces: `Principal(user_id: UUID, firm_id: UUID, role: Role)`.
- Produces: `require_roles(*roles: Role)` FastAPI dependency and `can_transition_review(role, old, new) -> bool`.
- Produces project list filters `search`, `status`, `review_status`, `limit`, `offset` and response `{items,total,limit,offset}`.

- [ ] **Step 1: Write failing role, tenant and project tests**

Cover valid/invalid sessions, `GET /auth/me`, all four permission matrices, reviewer mutation denial, lawyer approval denial, owner/admin deletion, cross-firm 404, search escaping, status filters, pagination totals, activity order and new project fields.

- [ ] **Step 2: Run the focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_authz.py services/api/tests/test_projects_step2.py -q`

Expected: FAIL because roles/routes/contracts are absent.

- [ ] **Step 3: Extend the principal and permission policy**

Resolve role from the active membership after JWT verification. Keep deterministic oldest-membership selection and development owner identity. Return 403 only for visible same-firm resources; tenant misses remain 404.

- [ ] **Step 4: Extend project schemas, queries and services**

Add `legal_area`, `language`, `target_audience`, `complexity`, owner, workflow status and processing status with bounded enums/strings. Implement parameterized case-insensitive search and stable `(updated_at DESC, id)` pagination.

- [ ] **Step 5: Split route modules and add auth/activity endpoints**

Keep `routes.py` as the aggregator. Ensure every mutation writes a metadata-only audit event and successful analysis later resets review status.

- [ ] **Step 6: Run auth/project regression tests**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_authz.py services/api/tests/test_projects.py services/api/tests/test_projects_step2.py -q`

Expected: all tests pass.

- [ ] **Step 7: Commit**

```powershell
git add services/api/app/core services/api/app/api services/api/app/schemas services/api/app/repositories services/api/app/services services/api/tests
git commit -m "feat: enforce firm roles and expand projects"
```

### Task 4: Build durable jobs and Celery plumbing

**Files:**
- Create: `services/api/app/schemas/jobs.py`
- Create: `services/api/app/repositories/jobs.py`
- Create: `services/api/app/services/jobs.py`
- Modify: `services/worker/celery_app.py`
- Create: `services/worker/tasks/__init__.py`
- Create: `services/worker/tasks/documents.py`
- Create: `services/worker/tasks/analysis.py`
- Modify: `infrastructure/docker/worker.Dockerfile`
- Modify: `docker-compose.yml`
- Test: `services/api/tests/test_jobs.py`

**Interfaces:**
- Produces: `create_job(db, principal, project_id, job_type, request_hash, idempotency_key) -> GenerationJob`.
- Produces: `transition_job(db, job_id, expected, target, *, stage, progress, error=None) -> GenerationJob` using compare-and-set semantics.
- Produces: Celery tasks accepting IDs only: `worker.parse_document(document_id, job_id)` and `worker.analyze_project(job_id)`.

- [ ] **Step 1: Write failing job state/idempotency tests**

Assert legal state transitions, monotonic 0–100 progress, duplicate idempotency-key reuse, one active analysis job per project, safe failure fields, retry count and tenant-scoped polling.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_jobs.py -q`

Expected: FAIL because job services are absent.

- [ ] **Step 3: Implement durable job repositories/services**

Use database uniqueness and compare-and-set updates rather than Redis state. Raw exception strings must not enter `error_message`; map known failures to safe error codes/messages.

- [ ] **Step 4: Make the worker import the API domain safely**

Copy `services/api/app` and `services/worker` into the worker image, set `PYTHONPATH`, share the private-storage named volume, configure Celery task modules, acknowledgements, retry backoff and soft/hard timeouts.

- [ ] **Step 5: Verify eager and live worker behavior**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_jobs.py -q; docker compose --profile app build worker`

Expected: tests pass and worker image builds.

- [ ] **Step 6: Commit**

```powershell
git add services/api/app/schemas/jobs.py services/api/app/repositories/jobs.py services/api/app/services/jobs.py services/worker infrastructure/docker/worker.Dockerfile docker-compose.yml services/api/tests/test_jobs.py
git commit -m "feat: add durable background jobs"
```

### Task 5: Implement private storage and upload admission

**Files:**
- Create: `services/api/app/integrations/storage.py`
- Create: `services/api/app/schemas/documents.py`
- Create: `services/api/app/repositories/documents.py`
- Create: `services/api/app/services/documents.py`
- Create: `services/api/app/api/documents.py`
- Modify: `services/api/app/api/routes.py`
- Modify: `apps/web/src/app/api/backend/[...path]/route.ts`
- Test: `services/api/tests/test_storage.py`
- Test: `services/api/tests/test_documents_api.py`

**Interfaces:**
- Produces `DocumentStorage.put(key, stream)`, `open(key)`, `delete(key)`, and `signed_url(key, expires_seconds)` protocol methods.
- Produces `LocalPrivateStorage` and `SupabasePrivateStorage`; neither returns a public URL.
- Produces upload endpoint returning HTTP 202 `{document, job}`.

- [ ] **Step 1: Write failing storage/upload tests**

Cover PDF/DOCX/TXT signature acceptance, extension/MIME mismatch, unsupported type, 25 MiB boundary, empty file, SHA-256, duplicate conflict, randomized tenant path, cross-firm project, reviewer denial, storage rollback and no public URL. Explicitly assert a `.pdf` body without `%PDF-` returns 415 and creates no row/object.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_storage.py services/api/tests/test_documents_api.py -q`

Expected: FAIL because storage/upload modules are absent.

- [ ] **Step 3: Implement streaming admission and storage adapters**

Read bounded chunks once while hashing and signature-sniffing into a server-managed temporary file. Generate object keys from trusted UUIDs. Use Supabase Storage REST only with the server-side service credential and configured private bucket; never expose it to Next.js.

- [ ] **Step 4: Implement document API and transactional cleanup**

Create the row/job only after validation; dispatch after commit. On database/storage/dispatch failure, remove exact temporary/private objects and return a safe error. Duplicate hashes return 409 with existing document ID/status only.

- [ ] **Step 5: Make the BFF preserve multipart streams**

Forward content type and authorization without parsing multipart as text. Enforce the configured upper bound using `Content-Length` when present and streaming cancellation otherwise; retain same-origin mutation checks.

- [ ] **Step 6: Run upload tests and inspect storage isolation**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_storage.py services/api/tests/test_documents_api.py -q`

Expected: all focused tests pass and test objects are cleaned.

- [ ] **Step 7: Commit**

```powershell
git add services/api/app/integrations/storage.py services/api/app/schemas/documents.py services/api/app/repositories/documents.py services/api/app/services/documents.py services/api/app/api/documents.py services/api/app/api/routes.py apps/web/src/app/api/backend services/api/tests/test_storage.py services/api/tests/test_documents_api.py
git commit -m "feat: add private document uploads"
```

### Task 6: Parse documents and retain chunk provenance

**Files:**
- Create: `services/worker/pipelines/documents.py`
- Create: `services/worker/pipelines/chunking.py`
- Modify: `services/worker/tasks/documents.py`
- Modify: `services/api/app/services/documents.py`
- Test: `services/api/tests/test_document_pipeline.py`

**Interfaces:**
- Produces `ExtractedDocument(text, pages, metadata, headings, ocr_required)` and `ExtractedPage(number, text, headings)`.
- Produces `parse_document_bytes(media_type, content) -> ExtractedDocument`.
- Produces `chunk_document(extracted, *, target_chars=2400, overlap_chars=300) -> list[DocumentChunkInput]` preserving page, heading, filename and offsets.

- [ ] **Step 1: Write failing parser/chunker tests**

Generate fixtures in tests and assert PDF pages, DOCX headings, TXT decoding, ordered chunks, overlap/provenance, empty TXT failure, corrupt PDF failure, scanned-PDF `ocr_required`, large-document bounds and idempotent rerun replacement.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_document_pipeline.py -q`

Expected: FAIL because parser/chunker functions are absent.

- [ ] **Step 3: Implement pure bounded parsers and chunking**

Use PyMuPDF, python-docx and bounded text decoding. Normalize control characters without rewriting quoted legal text. Never mark pages-without-text completed; set `ocr_required` with an actionable safe message.

- [ ] **Step 4: Implement the idempotent parse task**

Lock the document row, skip completed work with the same hash/parser version, update job progress, replace chunks transactionally, and check project/document existence before each durable write.

- [ ] **Step 5: Run parser and job tests**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_document_pipeline.py services/api/tests/test_jobs.py -q`

Expected: all tests pass.

- [ ] **Step 6: Commit**

```powershell
git add services/worker/pipelines services/worker/tasks/documents.py services/api/app/services/documents.py services/api/tests/test_document_pipeline.py
git commit -m "feat: parse and chunk legal documents"
```

### Task 7: Implement structured legal schemas and OpenAI provider contracts

**Files:**
- Create: `services/api/app/schemas/analysis.py`
- Create: `services/api/app/integrations/openai_provider.py`
- Create: `services/api/app/services/prompting.py`
- Test: `services/api/tests/test_analysis_provider.py`

**Interfaces:**
- Produces Pydantic `LegalProcess`, `ProcessStageOutput`, `CitationClaim`, `AnalysisRequest`, `EvidenceChunk`, and `EmbeddingBatch`.
- Produces `EmbeddingProvider.embed(texts: list[str]) -> EmbeddingBatch`.
- Produces `LegalAnalysisProvider.analyze(request: AnalysisRequest, evidence: list[EvidenceChunk]) -> LegalProcess`.
- Produces `get_embedding_provider(settings)` and `get_analysis_provider(settings)` that raise `ProviderUnavailable` rather than selecting test doubles.

- [ ] **Step 1: Write failing schema/provider tests**

Assert ordered unique stages, explicit jurisdiction, non-empty input, `review_required=true`, bounded text/list sizes, unknown evidence rejection, unsupported claim handling, missing citations, refusal handling, invalid structured response, one validation-repair retry and no retry for policy/configuration errors.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_analysis_provider.py -q`

Expected: FAIL because schemas/providers are absent.

- [ ] **Step 3: Implement strict Pydantic schemas and untrusted-evidence prompting**

Use `extra="forbid"`, explicit size bounds and cross-field validators. Delimit each evidence item with its opaque chunk ID and state that embedded instructions are data, not application commands. Require the model to distinguish source-backed claims from general explanation.

- [ ] **Step 4: Implement the OpenAI SDK adapters**

Use `OpenAI().responses.parse(model=settings.openai_analysis_model, input=..., text_format=LegalProcess)` and `client.embeddings.create(model="text-embedding-3-small", dimensions=1536, input=texts)`. Validate response count/order/dimensions and map refusals, timeouts, rate limits and malformed outputs to typed safe failures.

- [ ] **Step 5: Run provider tests with injected transports**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_analysis_provider.py -q`

Expected: all tests pass; no live request or key is used.

- [ ] **Step 6: Commit**

```powershell
git add services/api/app/schemas/analysis.py services/api/app/integrations/openai_provider.py services/api/app/services/prompting.py services/api/tests/test_analysis_provider.py
git commit -m "feat: add structured legal analysis provider"
```

### Task 8: Implement RAG retrieval, analysis orchestration and citation validation

**Files:**
- Create: `services/api/app/schemas/sources.py`
- Create: `services/api/app/repositories/analysis.py`
- Create: `services/api/app/repositories/sources.py`
- Create: `services/api/app/services/rag.py`
- Create: `services/api/app/services/citations.py`
- Create: `services/api/app/services/analysis.py`
- Create: `services/worker/pipelines/analysis.py`
- Modify: `services/worker/tasks/analysis.py`
- Test: `services/api/tests/test_rag.py`
- Test: `services/api/tests/test_analysis_pipeline.py`

**Interfaces:**
- Produces `retrieve_evidence(db, principal, project_id, query_vector, filters, limit, threshold) -> list[EvidenceChunk]`.
- Produces `validate_citations(process, evidence_by_id) -> CitationValidationResult`.
- Produces `run_analysis_job(job_id, providers) -> None`, publishing stages/citations/version atomically.

- [ ] **Step 1: Write failing retrieval/citation tests**

Cover firm/project/document/jurisdiction/source-type filters, threshold/limit order, user-document verification labels, exact excerpt membership, unknown IDs, missing citations and no-evidence behavior.

- [ ] **Step 2: Write failing orchestration tests**

Assert selected documents are embedded on demand only, failed/OCR/cross-firm documents block, no-selected-documents produces unverified general results, partial stages never publish, successful publication resets review status, delete-during-run publishes nothing, idempotent retry does not duplicate rows, and only the current active job can publish.

- [ ] **Step 3: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_rag.py services/api/tests/test_analysis_pipeline.py -q`

Expected: FAIL because RAG/orchestration modules are absent.

- [ ] **Step 4: Implement tenant-filtered vector retrieval and legal source contracts**

Use pgvector cosine distance with an exact 1536-dimensional query. Project user documents are eligible only when selected; curated sources require matching project or verified firm-wide scope. Return actual stored passages and metadata only.

- [ ] **Step 5: Implement citation validation and atomic publication**

Accept only retrieved chunk IDs, require cited excerpts to occur in stored content, label associations `supported|unverified|unsupported`, and never equate association with proof. Replace stages/citations and add a version snapshot in one transaction.

- [ ] **Step 6: Implement the analysis task chain**

At safe checkpoints verify job/project/document existence, embed selected chunks, retrieve, call analysis, validate, publish and complete. Retry only typed transient failures with bounded backoff; a single validation repair is handled inside the provider.

- [ ] **Step 7: Run RAG/orchestration tests**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_rag.py services/api/tests/test_analysis_pipeline.py -q`

Expected: all tests pass.

- [ ] **Step 8: Commit**

```powershell
git add services/api/app/schemas/sources.py services/api/app/repositories services/api/app/services services/worker/pipelines/analysis.py services/worker/tasks/analysis.py services/api/tests/test_rag.py services/api/tests/test_analysis_pipeline.py
git commit -m "feat: add tenant-safe RAG and citations"
```

### Task 9: Expose document, analysis, stage, citation and job APIs

**Files:**
- Modify: `services/api/app/api/documents.py`
- Create: `services/api/app/api/analysis.py`
- Modify: `services/api/app/api/routes.py`
- Modify: `services/api/app/main.py`
- Modify: `packages/contracts/openapi.json`
- Test: `services/api/tests/test_step2_api.py`

**Interfaces:**
- Produces all Step 2 endpoints from the approved design with existing error envelopes. `GET /projects/{project_id}/stages` returns current process-level metadata plus ordered stages; document detail may include only a short-lived signed download URL generated on demand.
- Consumes Task 4 job services, Task 5 document services and Task 8 analysis services.

- [ ] **Step 1: Write failing API contract tests**

Cover document list/detail/delete, short-lived private signed URL behavior, analysis 202, provider-disabled 503 code, selected-pending 409, job polling, current process metadata/stage list, stage detail, citation list, all role permissions, rate-limit headers and cross-firm 404. Assert unknown request fields return 422 and no endpoint returns hardcoded success.

- [ ] **Step 2: Run focused tests and confirm failure**

Run: `.\.venv\Scripts\python.exe -m pytest services/api/tests/test_step2_api.py -q`

Expected: FAIL on missing routes.

- [ ] **Step 3: Implement thin route handlers and rate limits**

Keep domain work in services. Use Redis fixed-window admission for uploads/analysis keyed by firm and user; return 429 with `Retry-After`. Add `Idempotency-Key` to CORS allowed headers and never include tokens/body content in logs.

- [ ] **Step 4: Export and inspect the OpenAPI contract**

Run: `.\.venv\Scripts\python.exe scripts/export_contracts.py`

Expected: contract contains every requested endpoint, schemas and status codes.

- [ ] **Step 5: Run the full backend suite**

Run: `.\.venv\Scripts\python.exe -m pytest -q --tb=short`

Expected: all Step 1 and Step 2 tests pass.

- [ ] **Step 6: Commit**

```powershell
git add services/api/app/api services/api/app/main.py services/api/tests/test_step2_api.py packages/contracts/openapi.json
git commit -m "feat: expose Step 2 workflow APIs"
```

### Task 10: Complete Supabase account lifecycle UI

**Files:**
- Modify: `apps/web/src/components/auth-form.tsx`
- Modify: `apps/web/src/hooks/use-session.ts`
- Modify: `apps/web/src/components/dashboard-shell.tsx`
- Create: `apps/web/src/app/forgot-password/page.tsx`
- Create: `apps/web/src/app/reset-password/page.tsx`
- Create: `apps/web/src/app/auth/callback/page.tsx`
- Create: `apps/web/src/components/password-recovery.tsx`
- Modify: `apps/web/src/components/settings.tsx`
- Modify: `apps/web/src/lib/validation.ts`
- Test: `apps/web/src/lib/validation.test.ts`
- Create: `apps/web/src/components/auth-flow.test.tsx`

**Interfaces:**
- Produces browser flows using Supabase `signUp`, `signInWithPassword`, `resetPasswordForEmail`, `exchangeCodeForSession`, `updateUser`, `resend`, and `signOut`.
- Consumes `GET /api/v1/auth/me` for firm/role display after a session exists.

- [ ] **Step 1: Add failing validation and auth-flow tests**

Test malformed email, login/registration password distinction, recovery success/error, expired callback, verification resend, reset confirmation mismatch, session expiry cache clearing and redirect, and local-mode absence of cloud-only controls.

- [ ] **Step 2: Run frontend tests and confirm failure**

Run: `npm.cmd test -w apps/web -- --run`

Expected: new auth tests fail.

- [ ] **Step 3: Implement recovery, verification and callback pages**

Use the existing Supabase browser client only; never add service-role values. Give each page one H1, unique metadata/canonical, accessible status/error messaging and links back to sign-in.

- [ ] **Step 4: Handle expiration and authenticated account context**

Subscribe to auth state changes, clear TanStack Query on sign-out/expiry and redirect safely. Settings shows actual email, verification state, active firm and role from verified APIs.

- [ ] **Step 5: Run unit, lint and type checks**

Run: `npm.cmd test -w apps/web -- --run; npm.cmd run lint; npm.cmd run typecheck`

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/app apps/web/src/components apps/web/src/hooks apps/web/src/lib
git commit -m "feat: complete account recovery and verification"
```

### Task 11: Build project creation, search and activity UI

**Files:**
- Create: `apps/web/src/app/dashboard/projects/new/page.tsx`
- Modify: `apps/web/src/app/dashboard/projects/page.tsx`
- Modify: `apps/web/src/components/projects.tsx`
- Modify: `apps/web/src/components/project-form.tsx`
- Create: `apps/web/src/components/project-filters.tsx`
- Create: `apps/web/src/components/project-activity.tsx`
- Modify: `apps/web/src/types/project.ts`
- Modify: `apps/web/src/lib/validation.ts`
- Test: `apps/web/src/components/projects.test.tsx`

**Interfaces:**
- Produces typed `Project`, `ProjectList`, `ProjectInput`, `ProjectActivity` matching Task 3 contracts.
- Consumes the existing `api<T>()` BFF client and notification store.

- [ ] **Step 1: Write failing UI tests**

Assert all new fields, whitespace/length validation, URL-backed search/status filters, debounced query behavior, honest empty/loading/error states, create/update/delete notifications and real activity rendering without fake counts.

- [ ] **Step 2: Run tests and confirm failure**

Run: `npm.cmd test -w apps/web -- --run`

Expected: new project UI tests fail.

- [ ] **Step 3: Implement types, validation, forms and filters**

Use a dedicated `/dashboard/projects/new` page and retain the existing detail edit flow. Keep query parameters shareable and reset pagination when filters change.

- [ ] **Step 4: Implement activity and permission-aware actions**

Render server-returned activity only. Hide unauthorized actions for usability while relying on backend enforcement; show explicit 403/404 messages if state becomes stale.

- [ ] **Step 5: Run frontend checks**

Run: `npm.cmd test -w apps/web -- --run; npm.cmd run lint; npm.cmd run typecheck`

Expected: all pass.

- [ ] **Step 6: Commit**

```powershell
git add apps/web/src/app/dashboard/projects apps/web/src/components apps/web/src/types/project.ts apps/web/src/lib/validation.ts
git commit -m "feat: expand project management workspace"
```

### Task 12: Build upload, analysis progress, stages and citation UI

**Files:**
- Modify: `apps/web/src/app/dashboard/projects/[id]/page.tsx`
- Create: `apps/web/src/components/project-workspace.tsx`
- Create: `apps/web/src/components/document-upload.tsx`
- Create: `apps/web/src/components/document-list.tsx`
- Create: `apps/web/src/components/analysis-form.tsx`
- Create: `apps/web/src/components/job-progress.tsx`
- Create: `apps/web/src/components/process-results.tsx`
- Create: `apps/web/src/components/citation-viewer.tsx`
- Create: `apps/web/src/services/uploads.ts`
- Create: `apps/web/src/types/document.ts`
- Create: `apps/web/src/types/analysis.ts`
- Modify: `apps/web/src/app/globals.css`
- Create: `apps/web/src/components/project-workspace.test.tsx`
- Modify: `apps/web/e2e/foundation.spec.ts`

**Interfaces:**
- Produces `uploadDocument(projectId, file, onProgress) -> Promise<UploadAccepted>` using XHR through the BFF.
- Produces polling queries for document/job state and typed results/citations.
- Consumes Tasks 5 and 9 APIs.

- [ ] **Step 1: Write failing component tests**

Cover file validation, real upload progress, duplicate/corrupt/OCR errors, delete confirmation, selected-document gating, provider-disabled message, queued/running/failed/completed job states, ordered stages, professional-review notice, source-type/verification badges and citation excerpt/page display.

- [ ] **Step 2: Run component tests and confirm failure**

Run: `npm.cmd test -w apps/web -- --run`

Expected: workspace tests fail.

- [ ] **Step 3: Implement the responsive project workspace**

Use accessible tab-like navigation that remains ordinary links/sections without JavaScript traps. Preserve one page H1, keyboard focus, 320 px layout and existing squared controls.

- [ ] **Step 4: Implement XHR upload and honest processing states**

Use actual `xhr.upload.onprogress`; do not simulate progress. Poll while document/job states are active, stop on terminal state/unmount and retain actionable failures.

- [ ] **Step 5: Implement analysis form, job progress, results and citations**

Require jurisdiction and process text, disclose external processing before selected documents are submitted, and render exactly the stored result. No image or diagram controls appear.

- [ ] **Step 6: Expand Playwright workflow**

Exercise local sign-in, project create with Step 2 fields, real TXT and generated DOCX/PDF uploads, processing completion, provider-unavailable analysis, save/reopen, deletion, console errors, keyboard behavior and 375/768/1024/1440 px overflow. Backend tests remain the authoritative cross-firm proof.

- [ ] **Step 7: Run unit and browser checks**

Run: `npm.cmd test -w apps/web -- --run; npm.cmd run test:e2e -- --reporter=line`

Expected: all component and browser tests pass.

- [ ] **Step 8: Commit**

```powershell
git add apps/web/src apps/web/e2e/foundation.spec.ts
git commit -m "feat: add document and legal analysis workspace"
```

### Task 13: Harden, integrate, verify and document Step 2

**Files:**
- Modify: `docker-compose.yml`
- Modify: `infrastructure/docker/api.Dockerfile`
- Modify: `infrastructure/docker/worker.Dockerfile`
- Modify: `.github/workflows/ci.yml`
- Modify: `README.md`
- Modify: `docs/architecture.md`
- Modify: `docs/quality-checklist.md`
- Modify: `docs/file-inventory.txt`
- Create: `docs/step-2-report.md`
- Modify: `scripts/verify.ps1`

**Interfaces:**
- Consumes every prior task; produces the verified local runbook and truthful blocker report.

- [ ] **Step 1: Run static, unit, migration and build checks**

Run:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
.\.venv\Scripts\python.exe scripts/audit_migrations.py
npm.cmd run build
```

Expected: Ruff, formatting, Pytest, Alembic drift, ESLint, TypeScript, Vitest and Next production build all pass.

- [ ] **Step 2: Build and start clean Docker images**

Run: `docker compose --profile app build; docker compose --profile app up -d --wait`

Expected: PostgreSQL, Redis, API and worker are healthy; API readiness verifies the new migration head.

- [ ] **Step 3: Execute the real local workflow**

Create/reopen/delete a project; upload and parse PDF, DOCX and TXT; inspect chunks/status; verify provider-disabled analysis returns the documented blocker; verify worker ping/task execution and persistence across PostgreSQL restart. Use only non-confidential generated fixtures.

- [ ] **Step 4: Run browser, dependency, secret and schema integrity checks**

Run Playwright, `npm audit --omit=dev`, `pip check`, tracked-secret pattern checks, invalid-index/unvalidated-constraint queries and Docker logs. Fix findings instead of suppressing them.

- [ ] **Step 5: Update documentation and 32-point checklist**

Record exact installed versions, migrations, endpoints, tests, live service status, security measures, RAG/provider behavior and commands. Mark live OpenAI generation and hosted Supabase Auth/Storage verification BLOCKED, not PASS, until credentials and processing approval exist.

- [ ] **Step 6: Perform a final security/code review and fix cycle**

Review tenant boundaries, file parsing/storage, deletion races, prompt injection, provider logging, error redaction and frontend regressions. Rerun every affected test after fixes.

- [ ] **Step 7: Commit**

```powershell
git add .github README.md docs scripts docker-compose.yml infrastructure
git commit -m "docs: finalize verified Step 2 delivery"
```

## Final acceptance boundary

The local workflow is complete when authentication/local access, project management, private upload, parsing, status polling, source inspection, save/reopen and cross-tenant denial all pass. With the current credential decision, the provider adapters, structured-output validation, embeddings/RAG orchestration and citation publication are fully automated against controlled transports, while an actual OpenAI-generated legal process and hosted Supabase Storage remain explicitly blocked. Step 3 must not begin.
