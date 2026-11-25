# ClientExplain AI: foundation decisions

Step 2 scope includes persistent tenant-aware projects, private uploads, asynchronous parsing, status polling, structured analysis adapters, embeddings, retrieval, citation publication and an editable workflow canvas. Local ingestion works without cloud credentials; failed documents can be retried and profile display names edited. Saved workflows can be downloaded as a PDF report and a locally generated PNG diagram; exports do not verify legal content. Live OpenAI and hosted Supabase Auth/Storage acceptance remain blocked pending credentials and external-processing approval. Real Ollama inference is not yet verified. Stage-specific illustrations, substantive lawyer-review history and version-history UI remain unimplemented. Every generated explanation requires professional review.

## Architecture

Use this existing workspace as the monorepo root; an additional nested clientexplain-ai directory would add no value. Next.js App Router talks to a versioned FastAPI modular monolith. PostgreSQL 16 with pgvector stores application data. Redis brokers Celery jobs in a separate process. No inference libraries load in the API.

Alternatives considered: a full local Supabase stack adds operational weight for a solo developer; cloud-only development requires credentials and network access. Selected: standalone local PostgreSQL plus optional hosted Supabase Auth. No migration references auth.users or auth.uid(). Profiles map verified Supabase subject UUIDs. Private storage uses a local named volume for development or a server-only Supabase private bucket adapter; public buckets are rejected.

Local development uses an explicitly enabled, random bearer token, a seeded development profile and firm, and loopback-bound services. Production configuration rejects this mode. Supabase mode verifies signed JWTs, issuer, audience and expiry, then provisions a personal workspace transactionally. Tenant identity is resolved from verified membership, never a client-supplied firm ID. Queries filter by firm. Composite foreign keys prevent cross-firm relations. PostgreSQL RLS adds defense in depth using transaction-local app.firm_id. Production must run a non-owner database role, with no BYPASSRLS permission. Supabase Data API access to application tables is not enabled.

## GPU and AI boundaries

Measured 2026-11-17: NVIDIA GeForce RTX 3050 6GB Laptop GPU, 6144 MiB VRAM, driver 610.47. No inference model has been benchmarked. Diffusion remains disabled pending model/license, VRAM, latency, safety and cost measurements. The separate Celery worker runs with concurrency one. OpenAI structured analysis and embeddings require explicit server and per-request processing consent. Local Ollama adapters are also implemented; their endpoint is restricted to local addresses, model installation is checked by `/api/v1/ai/status`, and the embedding adapter rejects vectors that do not match the fixed 1536-dimensional database contract. Tests use controlled transports; no paid AI call is required or claimed. Actual Ollama inference remains unverified. Active vectors retain provider/model metadata and cosine retrieval; legacy vectors are preserved separately by migration.

## Step 2 processing and integrity

Uploads admit only matching PDF, DOCX and UTF-8 TXT content up to 25 MiB. MIME/signature checks, bounded ZIP expansion, randomized tenant/project object keys and path containment precede parsing. The API streams to private storage and dispatches UUID-only Celery messages. API and worker use a shared private volume at `/var/lib/clientexplain/private-storage` under unprivileged users with matching UID; no document content is placed in broker messages. Parsing persists ordered chunks and source page/heading metadata. Scanned PDFs requiring OCR and malformed/password-protected documents return explicit errors.

Jobs have guarded transitions, active-job uniqueness, delivery retries, durable recovery intents and watchdog reconciliation. Failed document parsing can be retried; document deletion tombstones the source, invalidates dependent stages/citations, and queues storage cleanup. Project/document locks coordinate deletion, parsing and analysis publication; late deliveries cannot republish deleted sources. Status/progress is persisted in PostgreSQL. Redis fixed-window admission is tenant/user-scoped and fails closed when unavailable.

Analysis validates a structured process schema, treats retrieved passages as untrusted data and resolves citation IDs against stored eligible evidence. Tenant/project, jurisdiction, legal area and source-verification filters constrain retrieval. Unsupported claims cannot receive invented source citations. Stage rows, citations and version snapshots publish atomically after input fingerprint checks. Prompt injection mitigations and evidence checks do not establish legal correctness; a professional must review every generated explanation.

Canonical Alembic chain currently ends at `f4a8d1c7e902`, following the Step 2 core, illustration/review/export groundwork and a follow-up that preserves the review-stage foreign key on deletion. Readiness compares the installed head, database and Redis availability. The disposable migration audit exercises legacy data preservation, forced RLS and rollback guards. Apply migrations explicitly before application startup. Destructive downgrades refuse when Step 1 cannot represent current citations or pending recovery intents.

All routes are under `/api/v1`; `packages/contracts/openapi.json` is the exported API contract. Document collection/upload is `/projects/{id}/documents`; document inspection/deletion/retry is `/documents/{id}` and `/documents/{id}/retry`; analysis submission and provider status are `/projects/{id}/analyze` and `/ai/status`; profile reads/updates are `/auth/me`; polling is `/jobs/{id}`; workflow reads/updates are `/projects/{id}/workflow`; published reads are `/projects/{id}/stages`, `/stages/{id}` and `/projects/{id}/citations`. Authentication and tenant lookup precede role decisions to avoid cross-tenant existence probes. Error envelopes and logs omit secrets, raw provider exceptions and document text.

Workflow exports are generated in the browser from the saved editor graph. PNG contains a labeled SVG-derived diagram; PDF contains stage details, connections, version and review-status metadata. Neither export is persisted to the backend `exports` table or represents professional approval.

## Interface

Warm off-white background, charcoal type, restrained teal, squared rounded-corner controls, Lucide icons and accessible forms. No invented activity, metrics, legal conclusions, testimonials or unavailable actions. Landing page separates available project organization from planned generation. Privacy and terms are explicitly drafts requiring business and jurisdiction review. App pages are noindex; public canonical origin comes from configuration.

ReactBits official component catalog and installation documentation were inspected. Optional animation does not improve this foundation enough to justify its runtime/licensing cost; no ReactBits component is installed. shadcn/ui provides the button primitive; standard CSS handles subtle hover/focus states and honors reduced motion.

## References

- https://pro.reactbits.dev/docs/components
- https://pro.reactbits.dev/docs/installation
- https://nextjs.org/docs/app/getting-started/installation
- https://ui.shadcn.com/docs/installation/next
- https://supabase.com/docs/guides/auth/jwts
- https://huggingface.co/docs/diffusers/optimization/memory
- https://github.com/pgvector/pgvector
