# ClientExplain AI Step 2 Design

## Intent

Turn the audited Step 1 foundation into a working, tenant-safe legal-process workspace. A lawyer can manage a project, privately upload and parse source documents, submit a legal-process brief, queue analysis, and inspect structured stages with evidence and verification status. Every generated result remains explicitly subject to professional review.

Step 2 must build on the existing Next.js, FastAPI, PostgreSQL/pgvector, Redis and Celery architecture. It must not implement image generation, diagram editing, exports or Step 3 functionality.

## Goals

- Complete Supabase-compatible account flows while preserving clearly separated local development access.
- Enforce firm membership and owner/admin/lawyer/reviewer permissions in FastAPI and PostgreSQL tenant filters.
- Expand real project management with searchable fields, activity and processing/review status.
- Accept PDF, DOCX and TXT uploads through private storage, parse them in Celery, retain provenance and report unsupported scanned documents honestly.
- Use real OpenAI structured-output and embeddings adapters when explicitly configured and approved for external processing.
- Retrieve tenant- and project-scoped evidence with pgvector and associate only real chunk identifiers with stage citations.
- Validate model output and citation references, marking unsupported or unverified statements instead of inventing authorities.
- Deliver a responsive project workspace with upload progress, job polling, stages and citation inspection.

## Non-goals

- Image generation, diffusion models and visual prompts rendered as assets.
- React Flow editing, exports, approval/version-history UI or public sharing.
- Scraping legal websites or claiming official-source coverage.
- A local legal LLM substitute, synthetic legal output or fake citations when OpenAI is unavailable.
- Firm administration screens or invitations beyond the role-aware backend foundation required by Step 2.

## Anti-goals

- Sending confidential documents to an external model by default.
- Running parsing, embedding or analysis inside synchronous API requests.
- Trusting firm IDs, roles, citation IDs or storage paths supplied by a browser.
- Treating an uploaded document as verified law.
- Logging document bodies, prompts, access tokens or secrets.

## Constraints and current state

- Step 1 is committed and audited. Existing project CRUD, Supabase JWT validation, local access, RLS, BFF proxy and worker health task remain in place.
- Reserved document, chunk, source, stage, citation and job tables exist but require additive migration changes.
- No usable OpenAI key, Supabase project, private bucket or embedding model is configured in this checkout.
- Runtime AI operations must therefore fail with a precise configuration/approval error. Provider calls are tested with controlled mocked transports, never represented as live output.
- `apps/web/next-env.d.ts` was already modified by the local Next.js toolchain and is not part of this design unless its generated content is required by a build.

## Approaches considered

### 1. Credential-independent implementation with provider adapters (selected)

Build the production adapters and full local document/job workflow now. Mock only provider transports in automated tests. Require both credentials and an explicit external-AI approval setting before sending content. Without them, analysis is visibly unavailable rather than fabricated.

This preserves truthful behavior, provides deterministic tests and lets the owner add credentials later without redesigning the application.

### 2. Require live OpenAI and Supabase before implementation

This would give a live end-to-end provider demonstration immediately, but credentials are unavailable and it would block all document, authorization and UI work. The user chose not to make Step 2 dependent on that setup.

### 3. Substitute a local or rules-based legal generator

Rejected. A small local model is not part of the requested stack, has not been benchmarked, and would create a misleading legal-quality claim. A rules-based response would be fake AI output and violate the specification.

## Architecture

### Application boundaries

- Next.js remains the browser application and same-origin BFF. JSON calls continue through `/api/backend`; uploads use a streaming multipart BFF path with strict limits and no body logging.
- FastAPI remains a modular monolith for authentication context, authorization, metadata CRUD, upload admission, job creation and result reads.
- Celery performs parsing, chunking, embeddings, analysis and citation validation. Tasks are independently idempotent and update durable job progress.
- PostgreSQL remains the source of truth. Redis is the broker and rate-limit store, not durable job state.
- Private storage uses a `DocumentStorage` protocol. Local development stores files below an ignored, non-public root shared by API and worker. Supabase mode writes to a configured private bucket. Object keys are server-generated as `firm/project/document/random-name`; user filenames never become paths.

### Provider boundaries

- `EmbeddingProvider.embed(texts)` returns vectors plus provider/model/dimension metadata. The OpenAI implementation uses the configured embeddings model and validates every returned dimension before storage.
- `LegalAnalysisProvider.analyze(request, evidence)` returns a Pydantic-validated `LegalProcess`. The OpenAI implementation uses the Responses API structured-output facility.
- `AI_EXTERNAL_PROCESSING_ALLOWED` defaults false. A key alone is insufficient to transmit document content.
- Tests inject deterministic fake transports at the provider boundary. Runtime never selects a fake provider.

### Firm membership scope

Step 2 enforces roles for memberships that already exist and continues Step 1 personal-workspace provisioning. Invitation, membership administration and an active-firm switcher are outside this step. If a profile has multiple memberships in test or pre-provisioned data, the server continues to select the oldest active membership deterministically. A later firm-management feature must introduce an explicit server-validated active-firm selection rather than accepting arbitrary firm IDs.

### Embedding dimensions

`EMBEDDING_MODEL` and `EMBEDDING_DIMENSIONS` are a validated pair. A migration introduces a dimensioned vector column based on the explicitly selected configuration used by this release, with the selected model recorded on every chunk. Responses whose length differs are rejected before commit. Changing dimensions later requires a new migration and re-embedding job; the system does not silently mix dimensions.

## Data design

One additive Alembic revision will:

- Expand `firm_members.role` to owner, admin, lawyer and reviewer.
- Expand projects with legal area, language, target audience, complexity, owner, workflow status and processing status.
- Expand documents with original name, SHA-256, metadata, page count, parsing error, OCR-required flag, deletion fields and a firm/project hash uniqueness rule.
- Expand document chunks with page number, heading, token/character offsets, source filename and JSON metadata.
- Expand legal sources with source type, citation reference, effective/repeal dates, verification state, last verified time, metadata and optional project/document association.
- Expand source chunks with page/heading metadata and a configured vector dimension.
- Expand process stages with responsible party, required documents, estimated duration, source-backed/general explanation flags, limitations and verification status.
- Permit stage citations to reference exactly one document chunk or legal-source chunk; store claim text, excerpt and validation state.
- Expand generation jobs with `queued/running/completed/failed/cancelled`, job type, current stage, integer progress, safe error code/message, retry count, idempotency key, timestamps and request metadata.
- Add indexes for project filters/search, hash duplicates, job polling and vector similarity. Composite firm/project foreign keys remain mandatory.
- Update RLS coverage and database-maintained timestamps for all added fields/tables.

No migration references Supabase `auth.users` or `auth.uid()`.

`legal_sources` represents curated legislation, judgments, government publications and secondary material, not ordinary uploads. Step 2 supplies validated repository/service contracts for future controlled import but no public source-creation route and no scraping. Project-scoped sources are eligible only for that project; firm-wide sources require an explicit verified state. Uploaded documents remain `documents/document_chunks` and are always presented as user-provided, unverified evidence.

## Authentication and authorization

- Supabase signup, sign-in and sign-out remain browser SDK operations. Add confirmation callback, resend-verification, forgot-password and reset-password flows.
- The BFF forwards the Supabase access token; FastAPI verifies signature, issuer, audience, expiry and subject using JWKS.
- `GET /api/v1/auth/me` returns the verified profile, active firm and role. Local development returns the seeded owner identity and is rejected in production.
- Every protected endpoint resolves membership server-side. The principal contains user, firm and role; firm is never accepted from request data.
- Owner/admin: all Step 2 project/document operations. Lawyer: create/read/update projects, upload/delete documents, run analysis. Reviewer: read projects/documents/stages/citations and update review state, but cannot create, upload, analyze or delete. Project deletion is owner/admin only.
- Review writes are limited to project-level transitions among `requires_review`, `in_review` and `approved` through the project update service. Reviewer, admin and owner may transition review state; lawyers may submit for review but not approve. A successful new analysis resets the project to `requires_review`. Source verification changes have no public Step 2 route and require a future controlled source-management workflow.
- Cross-firm resources return 404 to avoid disclosing existence. Permission failures within a visible firm return 403.
- Session expiry clears cached application data and routes the user to sign-in with a useful message.

## Project management

- Extend create/update/read contracts with title, jurisdiction, legal area, language, target audience and complexity.
- List endpoint supports validated search, status and review-status filters, stable pagination and real result totals.
- Project detail aggregates documents, latest analysis job, stages and audit activity through separate query endpoints to avoid a single oversized response.
- Audit events record metadata changes, uploads/deletions, analysis requests, job outcomes and review changes without sensitive bodies.

## Document pipeline

1. API validates multipart metadata, declared and sniffed type, extension, size and authorization while hashing the streamed upload.
2. Duplicate firm/project hashes return a conflict referencing the existing document; bytes are not stored twice.
3. Storage adapter writes a server-generated private object key. Database row and parse job are created transactionally; orphan cleanup runs if either step fails.
4. Celery retrieves the object and parses PDF with PyMuPDF, DOCX with python-docx or UTF-8/UTF-16 TXT with bounded decoding.
5. Empty/corrupt/unsupported documents fail safely. A PDF with pages but no extractable text becomes `ocr_required`, not completed. Optional OCR remains provider-disabled unless configured.
6. Chunking preserves document ID, ordinal, page, heading, source filename, offsets and metadata. It uses bounded, overlapping paragraph/section chunks and never crosses document boundaries.
7. Parsing never transmits a document externally. When an authorized user submits analysis and explicitly selects documents, the job may embed only those selected chunks after the operator has enabled external processing and the UI has disclosed that transmission. A separate idempotent task records the exact provider/model/dimension. Otherwise parsing completes locally with `embedding_unavailable`, enabling source inspection without claiming RAG readiness.
8. Deletion removes database children and private object; retriable storage cleanup is tracked if the object service is temporarily unavailable.

Project deletion is a hard tenant deletion in Step 2: documents, chunks, stages, citations, jobs, generated process snapshots and stored objects are removed. The non-sensitive audit event identifying the deletion remains at firm scope. In-flight tasks check project/document existence and cancellation before each durable write, then exit without recreating deleted records. Document deletion likewise removes dependent chunks/citations and its object; snapshots that referenced the deleted document are removed or invalidated rather than retaining its text.

## RAG, legal analysis and citations

- Analysis input requires non-empty process text and explicit jurisdiction; category, audience, complexity, language and selected document IDs are validated against the project.
- Retrieval filters by firm, project/document selection, jurisdiction, source type and verification state before vector ranking. Limit and relevance threshold are configuration-bound.
- Evidence packets use opaque chunk IDs and delimit uploaded text as untrusted data. A fixed system instruction states that document instructions cannot alter application policy and that no authority, URL, date or deadline may be invented.
- The structured schema contains process name, jurisdiction, legal area, summary, applicability date, audience, complexity, ordered stages, missing information, limitations and `review_required=true`.
- Every stage includes title, plain-language explanation, responsible party, required documents, estimated duration, evidence chunk IDs and claim/citation pairs. Returned IDs must be a subset of retrieved evidence.
- Validation rejects missing jurisdiction, unordered/duplicate stage numbers, `review_required=false`, unknown evidence IDs and malformed citations. Safe transient provider failures may retry with bounded backoff; validation failures receive at most one repair attempt.
- Citation validation checks that referenced chunks exist in the tenant/project evidence packet and that the cited excerpt occurs in the stored passage. It marks each association supported, unverified or unsupported. It does not claim semantic proof merely because a citation exists.
- User documents are always labeled `user_document/unverified` unless an authorized reviewer changes source verification metadata. Official sources and URLs are never invented or auto-created.
- A successful job replaces the project’s current stages and citations in one transaction and records a version snapshot. Partial results are never published.

Analysis with no selected evidence is allowed because a lawyer may ask for a general process explanation. Every resulting claim/stage is visibly `unverified`, has no fabricated citation and carries the professional-review requirement. Explicitly selected documents must have completed local parsing and be eligible for the approved embedding dependency; failed or OCR-required selections cause a 409 response naming only the safe document status. The system never silently drops a selected document.

## Jobs

- Durable job records are created before Celery dispatch. Task arguments contain IDs only, never document text or tokens.
- An idempotency key covers firm, project, job type and request hash. Repeated requests return the existing active/completed job.
- Tasks use queued, running, completed, failed and cancelled states with current stage, 0–100 progress, retry count and timestamps.
- Only retryable storage/network/provider errors are retried. Validation, unsupported media and configuration errors fail immediately with safe codes.
- API polling returns durable state. Cancellation is represented in the data model; active hard cancellation is limited to safe task checkpoints.

Only one analysis job per project may be active. Duplicate submission of the same client idempotency key returns that job, including after completion; a deliberate new submission without that key may rerun the same brief. The immutable request hash includes the brief, parameters, selected document hashes, provider model and prompt/schema version. Evidence or configuration changes therefore cannot reuse stale work. A database uniqueness rule prevents overlapping active analysis jobs, so only the accepted current job can publish stages.

## API surface

- `GET /api/v1/auth/me`
- Existing project CRUD, extended with search/filter query parameters and fields
- `GET /api/v1/projects/{project_id}/activity`
- `POST/GET /api/v1/projects/{project_id}/documents`
- `GET/DELETE /api/v1/documents/{document_id}`
- `POST /api/v1/projects/{project_id}/analyze`
- `GET /api/v1/jobs/{job_id}`
- `GET /api/v1/projects/{project_id}/stages`
- `GET /api/v1/stages/{stage_id}`
- `GET /api/v1/projects/{project_id}/citations`

Responses use the existing centralized error envelope. Upload returns 202 with document and parse-job records. Analyze returns 202 with a durable job, or 503 with an explicit configuration/approval code when no real provider may run.

## Frontend experience

- Preserve the Step 1 shell and visual system. Remove foundation-release copy where functionality now exists.
- Dashboard shows honest recent projects/jobs and actionable empty states, never fabricated totals.
- Projects page adds search/status filters and a dedicated new-project route/form with all Step 2 fields.
- Project detail becomes a workspace with Overview, Documents, Analysis and Activity sections that remain usable at 320–1440 px.
- Upload uses XHR for actual progress, accessible validation, duplicate/error messages and per-document processing states.
- Analysis form captures process text, jurisdiction, category, audience, complexity, language and selected documents.
- Job polling shows real stages/progress. Completed analysis renders ordered process stages, professional-review notice and citation badges.
- Citation viewer shows source type, verification status, filename/title, page/section and exact stored excerpt. It never labels a user upload official.
- Settings adds account email, verification state, password-recovery entry and current firm/role. No service-role data reaches the browser.

## Security and privacy

- Private storage only; no public bucket or permanent URL. Any future download URL is signed and short-lived.
- File signatures, extensions, MIME, size and safe filenames are validated; parsers run in the worker with time and memory/file-size bounds.
- Upload and analysis admission use Redis rate limits keyed by firm and user.
- Logs contain request/job/resource IDs and safe codes only. Provider logging is disabled for bodies; no document text, tokens or secrets are logged.
- External AI transmission requires explicit operator opt-in and UI disclosure. The request includes only selected/retrieved passages, not every project document.
- Delete workflows remove dependent chunks/citations and private objects, and create non-sensitive audit records.
- Existing CORS, same-origin local-session checks, secure error handling, RLS and composite tenant constraints remain regression-tested.

## Error handling

- 400 for malformed domain requests, 401 invalid/expired session, 403 insufficient same-firm role, 404 missing/cross-firm resource, 409 duplicate upload/job conflict, 413 oversized upload, 415 unsupported media, 422 schema validation, 429 rate limit, 503 unavailable provider/storage/queue.
- Background failures expose a safe error code and user-actionable message; detailed exceptions stay out of API responses and sensitive logs.
- The UI retains user input on recoverable errors and provides retry only where the operation is idempotent.

## Testing and acceptance

- Backend tests cover JWT/session paths, all four roles, cross-firm access, CRUD/search/filter, upload validation/duplicates/corruption/OCR-required state, parsers/chunks/provenance, storage cleanup, job transitions/retry/idempotency, provider validation, retrieval filtering and citation association.
- Worker tests run in eager mode with temporary private storage and injected provider transports.
- Frontend unit tests cover forms and state rendering; Playwright covers the controlled local workflow through parsing, provider-unavailable analysis, project reopen and cross-tenant API tests on the backend.
- Provider contract tests prove structured requests/responses without claiming a live OpenAI call. Live OpenAI/Supabase verification remains blocked until credentials and explicit data-processing approval exist.
- All Step 1 lint, type, build, migration, browser, accessibility and responsive checks must continue to pass.

## External blockers and truthful completion

Locally verifiable Step 2 can include authentication integration, authorization, project management, private local storage, parsing, chunking, jobs, provider contracts, RAG persistence/retrieval logic and the full UI. A real generated legal process and hosted Supabase Storage cannot be claimed in this environment. The final report must mark those live-provider portions BLOCKED, identify the exact configuration needed, and distinguish them from implemented/tested integration code.

## Builder decisions left open

- Exact file splits should follow the existing modular-monolith conventions, keeping parsing, storage, providers, authorization and tasks separately testable.
- Select current supported OpenAI model names only after checking official documentation during implementation; record exact names and dimensions in configuration and docs.
- Choose conservative upload, chunk-size, retrieval and rate-limit defaults, document them, and make them configurable.
