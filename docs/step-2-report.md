# Step 2 verification report

Verification date: 2026-11-23. Scope is the Step 2 core application. Step 3 has not started and is not authorized. Only non-confidential generated fixtures and controlled provider transports are used. No live OpenAI generation or hosted Supabase verification is claimed.

## Checks executed

| Check | Result / evidence |
|---|---|
| Ruff check and formatting | PASS: 71 Python files formatted; all checks passed |
| Full backend suite | PASS: 357 tests; PostgreSQL/Redis integration included |
| Alembic schema drift | PASS: no new upgrade operations |
| Disposable migration audit | PASS: upgrade, forced RLS, legacy data preservation, recovery-intent and citation rollback guards, downgrade and re-upgrade |
| ESLint / TypeScript | PASS: npm run lint and npm run typecheck |
| Full frontend unit suite | PASS: 79 tests in 5 files |
| Next production build | PASS: Next.js 16.4.6; all 17 static pages generated |
| Production npm dependencies | PASS: npm audit --omit=dev found 0 vulnerabilities |
| Python dependency consistency | PASS: pip check found no broken requirements |
| Clean Docker build | PASS: docker compose --profile app build --no-cache built API, worker and watchdog |
| Docker startup / readiness | PASS: up -d --wait; PostgreSQL, Redis, API and worker healthy; watchdog running |
| Worker ping | PASS: celery inspect ping returned one node and pong |
| Real generated workflow | PASS: create project, upload TXT/DOCX/PDF through API, real worker completion, stored chunks inspected, provider-disabled 503, reopen, delete and post-delete 404 |
| Schema integrity | PASS: zero invalid indexes and zero unvalidated constraints; installed Alembic head d14c3a7f2901 |
| Tracked secret patterns | PASS: no OpenAI/GitHub credential or private-key header matches in tracked files; pattern scan is not a full secret audit |
| Docker logs | Reviewed: API/worker startup successful; database logs contain expected rejected constraint/RLS/lock-timeout and rollback-guard probes from negative tests |
| Fresh Playwright / screenshots | BLOCKED in Task 13: existing development server and browser processes were preserved at coordinator instruction; no fresh browser PASS is claimed here |
| PostgreSQL restart persistence | NOT REPEATED in Task 13: preserving concurrently running verification processes; relational persistence/reopen is covered by integration tests |
| GitHub-hosted CI | NOT RUN: workflow updated locally; no hosted CI result claimed |

The final local `scripts/verify.ps1` command now includes migration audit, pip check, production npm audit and production build. `-Browser` additionally runs Playwright against already-running web/API/worker services. The extended script also completed successfully: 357 backend tests, 79 frontend tests, all lint/type/schema/migration/dependency checks and production build. Rerun after any further code change.

## Installed runtime and dependencies

Windows Python 3.11.9; project Node 22.23.5; Docker Engine 28.5.1; Compose v2.40.3-desktop.1. Live containers report PostgreSQL 16.16, pgvector 0.8.7 and Redis 7.4.12. Locked application dependencies include FastAPI 0.163.1, SQLAlchemy 2.0.58, Celery 5.7.0, OpenAI SDK 2.54.0, PyMuPDF 1.28.2, python-docx 1.2.0, Next.js 16.4.6, React 19.3.1, TypeScript 6.0.3, Vitest 5.1.0 and Playwright 1.65.1. Full versions are authoritative in `requirements.lock` and `package-lock.json`; Docker base-image tags can advance independently.

## Implemented workflow and interfaces

Local authentication, project create/edit/reopen/delete, role and tenant denial, private PDF/DOCX/TXT upload, asynchronous parsing, persisted chunks, job polling and document deletion are implemented. Uploads are capped at 25 MiB and require matching extension/media type/content checks. DOCX ZIP expansion and parser failures are bounded; scanned PDFs requiring OCR return an explicit state. The local private volume is shared at `/var/lib/clientexplain/private-storage` by API and worker users with matching unprivileged UID, preserving existing volume contents. Watchdog reconciliation handles durable recovery intents.

Canonical migration chain: `b83406a26f40` → `c62fbd003112` → `a27d9c4e8b11` → `d14c3a7f2901`. Migrations are explicit operator actions. Readiness verifies installed head, PostgreSQL and Redis; the worker healthcheck verifies its own node responds.

All routes below have `/api/v1` prefix. Project CRUD remains `/projects` and `/projects/{id}`. Upload/list: `/projects/{id}/documents`; document detail/delete: `/documents/{id}`; analysis: `/projects/{id}/analyze`; job polling: `/jobs/{id}`; process/stage/citation reads: `/projects/{id}/stages`, `/stages/{id}`, `/projects/{id}/citations`. See `packages/contracts/openapi.json` for request/response details.

Structured analysis, embeddings, RAG and citation publication are automated with controlled HTTP transports. Embeddings use `text-embedding-3-small`, 1536 dimensions. Retrieval reads actual stored passages with tenant/project and configured source filters, limit 8 and similarity threshold 0.35 by default. User documents remain unverified. Provider output must satisfy the structured schema; citation references resolve against stored eligible evidence. Published stages, citations and version metadata commit atomically after fingerprint checks. General guidance is distinguished from source-backed claims. Professional review remains mandatory.

## Security and review boundary

Review covered tenant predicates and composite foreign keys, restricted-role RLS, role permissions, storage key containment, bounded admission/parsing, deletion races, durable retry/recovery, evidence provenance, prompt injection, private request/provider logging and sanitized errors. Existing suites exercise these paths. Redis admission is user/tenant-scoped and fails closed. API/worker run unprivileged; secrets remain in ignored environment files. The original dirty `next-env.d.ts` and BFF route were preserved and excluded from the Task 13 commit.

This configuration remains local development infrastructure: loopback ports, local development identity, and database bootstrap owner. Production needs restricted runtime roles, verified hosted storage policies/authentication, TLS, backup/restore and retention review, deployment controls and jurisdiction-specific legal review. Automated prompt and provenance checks do not certify legal accuracy.

## External blockers

- **BLOCKED: actual OpenAI-generated legal process.** No approved credential/model configuration or external processing approval exists. Keep `AI_EXTERNAL_PROCESSING_ALLOWED=false`. Disabled analysis returns HTTP 503 and publishes no fabricated output. Live embeddings, retrieval quality, latency and costs require later approved verification.
- **BLOCKED: hosted Supabase Auth and Storage.** Real registration/confirmation/login/recovery and private bucket/policy behavior need a configured project and server-only credentials. Adapter/JWKS behavior is tested locally with controlled transports; hosted behavior is unverified.
- **Deferred stages:** diffusion, diagram editing, approval UI, version-history UI and exports remain outside Step 2. Do not begin Step 3.

## Repeatable commands

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
.\.venv\Scripts\python.exe scripts/audit_migrations.py
docker compose --profile app build --no-cache
docker compose --profile app up -d --wait
docker compose --profile app exec worker celery -A worker.celery_app:app inspect ping
# With the web frontend running and Chromium installed:
npm.cmd run test:e2e
docker compose --profile app ps
```

Do not point integration or migration audits at production. Do not remove Docker volumes to repeat checks; `down` preserves data and `down -v` deletes it.
