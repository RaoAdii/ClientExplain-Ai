# ClientExplain AI: foundation decisions

Step 1 scope: responsive public pages, authentication integration, a real persistent project workspace, tenant-aware API, relational schema, migrations, isolated worker, and repeatable quality checks. Generation, uploads, editing diagrams, citations, approval workflows and exports are later steps. All future generated explanations require professional review.

## Architecture

Use this existing workspace as the monorepo root; an additional nested clientexplain-ai directory would add no value. Next.js App Router talks to a versioned FastAPI modular monolith. PostgreSQL 16 with pgvector stores application data. Redis brokers Celery jobs in a separate process. No inference libraries load in the API.

Alternatives considered: a full local Supabase stack adds operational weight for a solo developer; cloud-only development requires credentials and network access. Selected: standalone local PostgreSQL plus optional hosted Supabase Auth. No migration references auth.users or auth.uid(). Profiles map verified Supabase subject UUIDs. Private storage integration is reserved for document work in Step 2, with no public buckets or upload claims in Step 1.

Local development uses an explicitly enabled, random bearer token, a seeded development profile and firm, and loopback-bound services. Production configuration rejects this mode. Supabase mode verifies signed JWTs, issuer, audience and expiry, then provisions a personal workspace transactionally. Tenant identity is resolved from verified membership, never a client-supplied firm ID. Queries filter by firm. Composite foreign keys prevent cross-firm relations. PostgreSQL RLS adds defense in depth using transaction-local app.firm_id. Production must run a non-owner database role, with no BYPASSRLS permission. Supabase Data API access to application tables is not enabled.

## GPU and AI boundaries

Measured 2026-11-17: NVIDIA GeForce RTX 3050 6GB Laptop GPU, 6144 MiB VRAM, driver 610.47. No model selected or benchmark claimed. Provider protocol permits local Diffusers and hosted adapters. Generation is disabled until a model/license, peak VRAM, latency, safety controls and fallback costs are measured. Concurrency one for the GPU worker. OpenAI structured analysis and embeddings are later steps; no API key or paid request is needed for Step 1. Vector columns have unspecified dimensions and store embedding model metadata; an indexed dimension must be chosen with the actual embedding model in Step 2.

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
