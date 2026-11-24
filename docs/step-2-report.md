# Step 2 verification report

Verification dates: 2026-11-23 through 2026-11-24. Scope is the Step 2 core application. Step 3 has not started and is not authorized. Only non-confidential generated fixtures and controlled provider transports are used. No live OpenAI generation or complete hosted Supabase application-auth verification is claimed.

## Final status

**BLOCKED** — all locally reproducible Step 2 code, migration, isolated Docker, real-worker ingestion and desktop/mobile Playwright checks pass. Final external acceptance remains blocked on live hosted Supabase Auth/Storage verification and approved live OpenAI processing credentials. These external checks were not simulated or marked as passing.

## Step 2.1 — External Integration Acceptance

Verification date: 2026-11-23. Permanent ignored environment files were inspected only for variable presence and consistency; no credential, token, identity, project reference or complete URL was printed or recorded. No normal Docker service, normal PostgreSQL data, persistent volume, existing account or existing storage object was changed. Controlled suites used only the isolated E2E database and cleaned their test records through existing fixtures.

### Supabase configuration audit — PASS

- Backend configuration contains `SUPABASE_URL`, `SUPABASE_PUBLISHABLE_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, and `SUPABASE_STORAGE_BUCKET`; permanent backend auth and storage modes are Supabase.
- Frontend configuration contains only `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` for Supabase. No service-role variable is present in the frontend environment or frontend source.
- Backend/frontend URL and publishable-key configuration match without exposing their values. The configured private bucket name is `clientexplain-private`.
- The browser client uses PKCE and disables automatic URL-session detection. Registration and recovery supply the explicit `/auth/callback` redirect. The callback requires a code, rejects provider error parameters, performs one guarded `exchangeCodeForSession`, clears cached workspace data, and restricts the post-callback destination.
- Session handling checks the local SDK session, revalidates the user with Supabase, forwards only the access token to the same-origin BFF, reacts to refresh/update/sign-out events, clears cross-account query state and redirects expired sessions.
- FastAPI verifies ES256/RS256 JWT signature, issuer, audience, expiry and UUID subject through the hosted JWKS endpoint. Membership is resolved server-side; tenant context and project/document predicates remain application-enforced before server-only storage access.
- `SupabasePrivateStorage` authenticates only server-side, refuses buckets whose metadata reports `public != false`, rejects unsafe object keys, disallows upsert, bounds signed URL lifetime and validates the returned signed path.

### Supabase Auth — BLOCKED

Live read-only provider checks succeeded: hosted JWKS returned HTTP 200 with signing keys, Auth settings returned HTTP 200 with the publishable key, and `/auth/v1/user` rejected a request without a user access token. Controlled authentication/authorization tests are included in the 172-test focused suite below.

Full live acceptance was not attempted because no dedicated test-account email/password configuration is available. The existing real account was not used, modified or deleted, and no unconfirmed account was created merely to satisfy automation. Consequently registration, email confirmation, login, callback, refresh, logout, authenticated project creation, two-account tenant isolation and role permissions remain BLOCKED pending dedicated test accounts and any required manual email confirmation.

### Supabase Storage — BLOCKED

Live server-adapter evidence succeeded against the configured hosted bucket using one uniquely named harmless synthetic text object:

- Bucket metadata reported private.
- Upload succeeded without upsert.
- Authenticated server read returned exactly the uploaded bytes.
- A 60-second signed download returned HTTP 200 and exactly the uploaded bytes with binary content metadata.
- Anonymous direct object access was rejected.
- The adapter deleted the synthetic object.
- A guarded audit of the dedicated `external-verification/` prefix found zero remaining synthetic objects. No existing object was listed by name, modified or deleted.

One initial metadata connection attempt encountered a transient `ConnectError`; a bounded read-only retry and the complete object lifecycle then succeeded. Overall Storage acceptance remains BLOCKED because upload/download through a real authenticated application session, unauthorized-user rejection and two-account cross-tenant rejection require the dedicated Supabase accounts missing above. The bucket was never made public and no policy was changed.

### OpenAI structured output — BLOCKED

No live OpenAI call was made. `OPENAI_API_KEY` and `OPENAI_ANALYSIS_MODEL` are not configured and `AI_EXTERNAL_PROCESSING_ALLOWED` is false, so there is neither a credential nor explicit processing approval. Model compatibility and live pricing therefore cannot be evaluated without guessing. The runtime correctly refuses provider construction/submission in this state.

The implementation uses the OpenAI Responses structured-output parser with the configured model, strict Pydantic JSON schema, `store=false`, a 60-second SDK timeout, SDK retries disabled, at most one schema repair, bounded inputs/evidence, refusal/truncation handling and sanitized typed failures. Durable Celery ownership performs limited retry handling without duplicating completed/idempotent submissions.

### Embeddings and RAG — BLOCKED

No live embedding was generated because OpenAI is unconfigured and unapproved. The controlled contract fixes the model to `text-embedding-3-small` with 1,536 dimensions, matching the PostgreSQL vector column and indexes. Tests verify response count/order/model/dimensions, finite vectors, bounded batches, tenant/project retrieval filters, verified-source handling, exact excerpts, unsupported/general claims, citation provenance and cross-tenant exclusion. Live storage/retrieval of an actual provider vector remains BLOCKED with the OpenAI prerequisites.

### External end-to-end workflow — BLOCKED

The local real-worker workflow remains PASS for project creation, private TXT/DOCX/PDF parsing, chunking, persistence, provider-disabled response, UI behavior and cleanup. A hosted end-to-end flow from Supabase-authenticated upload through live embedding, retrieval, structured generation, citation validation and frontend display was not attempted because dedicated Supabase accounts and all OpenAI prerequisites are missing. No image generation was attempted or claimed.

### Step 2.1 tests and evidence

```powershell
# Process-local settings targeted the isolated local database and Redis DB 15.
.\.venv\Scripts\python.exe -m pytest `
  services/api/tests/test_authz.py `
  services/api/tests/test_storage.py `
  services/api/tests/test_document_pipeline.py `
  services/api/tests/test_analysis_provider.py `
  services/api/tests/test_analysis_pipeline.py `
  services/api/tests/test_rag.py -q
```

Result: **172 passed in 12.78 seconds**. This is controlled/local evidence and is not mislabeled as live OpenAI or full live Supabase acceptance. No application code, migrations, policies, dependencies, tests or environment files were changed during Step 2.1; only this report was updated.

To unblock external acceptance safely:

1. Configure two dedicated non-production Supabase test accounts in separate firms and complete the provider's real email-confirmation flow without weakening it.
2. Provide an approved development OpenAI credential and an explicit Responses structured-output-capable model through the ignored server environment.
3. Obtain explicit authorization to set `AI_EXTERNAL_PROCESSING_ALLOWED=true` for the smallest synthetic paid smoke tests. Before calls, confirm current official model compatibility/pricing and provide a cost estimate for approval.
4. Rerun the required live Auth, application-level Storage isolation, structured generation, embedding, RAG/citation and end-to-end synthetic workflow checks. Until all succeed, overall status remains **BLOCKED**.

## Step 2.2 — Live Supabase Auth and Application Storage Verification

Verification date: 2026-11-24. Permanent Supabase mode remained enabled for the normal application. Environment files were inspected only for variable presence and cross-file consistency; no value, account identity, token, cookie, signed URL, private object path or complete connection string was printed or recorded. Normal Docker services, PostgreSQL databases/volumes, Supabase configuration, existing accounts and existing storage objects were not modified.

### Prerequisite and implementation audit

| Check | Status | Evidence |
|---|---|---|
| Dedicated Account A and mailbox | **PASS** | Required values were loaded from the ignored `.env.step22.local` without display. Password login succeeded and provider metadata confirmed the dedicated account is email-confirmed. |
| Dedicated Account B and mailbox | **PASS** | Required values were loaded from the same ignored file. It authenticated as a separate confirmed Supabase subject and provisioned a distinct application firm. |
| Supabase configuration consistency | **PASS** | Backend auth/storage and frontend auth are in Supabase mode; backend/frontend URL and publishable-key values match without revealing them. The service-role key is present only in backend configuration. |
| Current auth flow | **PASS (inspection/controlled)** | The browser uses Supabase PKCE, registration supplies the explicit same-origin callback, the callback exchanges one code and permits only `/reset-password` or `/dashboard`, the session hook revalidates with `getUser`, and the BFF forwards only the current bearer token. |
| Current backend/storage flow | **PASS (inspection/controlled)** | FastAPI validates signature, issuer, audience, expiry and UUID subject; resolves membership server-side; sets both tenant session variables; scopes project/document queries by firm; creates private object keys from firm/project/document UUIDs; and uses the backend-only service key. |

The live mutation gate passed. Only one uniquely named synthetic Account A project/document was created, and exact-resource cleanup completed. No administrative account shortcut, confirmation bypass, personal account, public bucket, RLS change or service-role authorization bypass was used for acceptance.

### Supabase Auth results

| Required result | Status | Evidence |
|---|---|---|
| Registration and validation | **NOT TESTED (this run)** | Both accounts were registered before execution. Provider metadata corroborated their existence and confirmation, while controlled UI validation remains passing; registration was not repeated. |
| Email confirmation | **PASS** | Both authenticated provider user records contained confirmation timestamps; confirmation was not bypassed. |
| Duplicate registration | **NOT TESTED (live)** | Existing dedicated identities were not re-registered. Controlled provider-error handling remains passing. |
| Login / incorrect password | **PASS** | Both password logins succeeded; a deliberately incorrect Account A password was rejected. Browser Account A login reached the dashboard. |
| Callback | **BLOCKED (provider rate limit)** | A fresh disposable signup through `/register` was attempted, but hosted Supabase returned HTTP 429 `over_email_send_rate_limit` before sending confirmation mail. No fresh code existed to exchange; controlled callback validation remains passing. |
| Session persistence | **PASS** | Repeated backend identity calls remained stable for both accounts; browser Account A remained authenticated after reload. |
| Session refresh | **PASS** | Both live refresh tokens produced new valid sessions that the application backend accepted. |
| Logout | **PASS after targeted fix** | Provider logout and refresh-token revocation passed for both accounts. After a RED→GREEN frontend fix, both live browser accounts logged out to clean `/login` with no expiration query or page error. |
| Backend JWT verification | **PASS** | Real JWTs for both accounts passed hosted user validation and application backend verification; malformed JWT was rejected with HTTP 401. |
| Development-auth production bypass | **PASS** | Permanent backend/frontend modes remained `supabase`; development authentication is separately gated and prohibited when `APP_ENV=production`. |

### Application Storage and tenant-isolation results

| Required result | Status | Evidence |
|---|---|---|
| Account A project creation | **PASS** | Account A created one uniquely named synthetic project through the same-origin application BFF; HTTP 201. |
| Application-level TXT upload | **PASS** | Account A uploaded one synthetic TXT through the BFF; HTTP 202. No service-role upload was substituted. |
| Authorized metadata/read/download | **PASS** | Account A listed and read its document and downloaded exact bytes through a 300-second signed URL. |
| Account B project/document/storage denial | **PASS** | Six Account B project/document read, download and deletion attempts returned non-disclosing HTTP 404 responses; direct private-storage read was also denied. |
| Anonymous application access | **PASS (negative check)** | The BFF rejected missing authorization with HTTP 401; FastAPI rejected missing authorization with HTTP 401. Provider-level anonymous private-object rejection remains separately recorded in Step 2.1. |
| Object-path manipulation | **PASS (controlled)** | Object keys reject absolute paths, traversal, backslashes, empty/dot segments and colon-based paths; object keys are generated server-side rather than accepted from the browser. |
| Upload validation | **PASS (controlled)** | The API enforces one file, 25 MiB maximum, PDF/DOCX/TXT allow-list, matching MIME/extension/signature, UTF-8 text and non-empty content. |
| Synthetic data cleanup | **PASS** | Account A deleted the exact document and project through application endpoints. Exact database project/document/job counts were zero and the exact private storage object no longer returned content. |

### Live execution evidence and targeted logout fix

- Two confirmed, distinct Supabase subjects authenticated and provisioned distinct application firms with owner roles.
- Both sessions persisted through repeated backend identity reads and refreshed successfully; malformed JWT was rejected.
- Account A application flow: project HTTP 201, TXT upload HTTP 202, authorized listing/detail HTTP 200, exact signed download bytes, document/project deletion HTTP 204.
- Account B isolation: six identifier-based project/document operations returned HTTP 404 and exposed no signed URL; anonymous BFF operations returned HTTP 401; Account B and anonymous direct storage reads were denied.
- Cleanup completed before the browser defect was encountered: exact project, document and generation-job counts were zero and the exact storage object was absent.
- Reproducible defect root cause: `DashboardShell.signOut()` called Supabase logout and intended `router.replace("/login")`, while `useSession` independently interpreted every SDK `SIGNED_OUT` event as expiration, emitted the expiration notification and called `router.replace("/login?reason=session-expired")`. Existing tests covered unexpected `SIGNED_OUT`, but no test distinguished an explicit user logout.
- Targeted fix: `DashboardShell` now sets a component-scoped explicit-logout intent ref before invoking Supabase. `useSession` still cancels requests and clears all query/session state on `SIGNED_OUT`, but suppresses expiration messaging/navigation while that intent is active; the dashboard action performs the single normal `/login` redirect. A failed logout resets intent so a later unexpected expiration keeps the existing protected behavior.
- TDD evidence: focused RED had 2 failures out of 26 tests, showing one and two erroneous expiration redirects respectively. Focused GREEN passed 26/26, including explicit redirect, state clearing, repeated-event stability and unchanged unexpected-expiration behavior.
- Live post-fix evidence: both dedicated accounts passed browser login, reload persistence and explicit logout to clean `/login`; both runs reported zero page errors.

### Fresh disposable confirmation-callback attempt — BLOCKED

On 2026-11-24, a fresh disposable Gmail plus-alias was generated from the user-selected Primary mailbox and submitted through the actual `/register` page in a browser retaining the PKCE verifier. No email address, password, confirmation URL, code or session token was printed or recorded.

- An initial harness-generated 73-character password was rejected by Supabase with HTTP 400 `validation_failed`. No confirmation message or user remained; the ignored harness was corrected to a shorter generated password. This was a verification-harness issue, not an application change.
- The corrected real application signup reached hosted Supabase but returned HTTP 429 `over_email_send_rate_limit` before confirmation email delivery.
- Per the acceptance instruction, execution stopped without another retry. No confirmation URL was opened, no callback code was exchanged, and no authenticated disposable session was claimed.
- Cleanup audit found **0** matching disposable users, **0** deletions required and **0** remaining disposable users. The short-lived mailbox, confirmation-URL and cleanup-state IPC files were absent.
- No Supabase policy, Auth setting, RLS policy, migration, application source file or normal Docker service was modified during this callback attempt.

### Security evidence

- Exact service-role value scan found zero matches under frontend source/build inputs; no frontend service-role variable is configured.
- The latest 500 normal API log lines contained zero bearer/JWT/authorization-header credential patterns. API request logging records only request ID, method, status and duration.
- A request from an unconfigured origin received no `Access-Control-Allow-Origin`; the configured localhost origin was returned explicitly. Wildcard CORS is rejected by configuration and credentialed CORS is disabled.
- Supabase mode uses the browser SDK session rather than an application auth cookie, so application cookie attributes are not applicable to the live Supabase flow. The development cookie path is not enabled by the permanent configuration.
- The tenant migration enables and forces RLS. Controlled database tests run against the isolated `clientexplain_e2e` database; RLS was not disabled or altered.
- The storage adapter refuses a public bucket, disallows upsert, validates object keys, caps signed URLs at 3600 seconds, and checks the provider-returned signed path.

### Step 2.2 regression evidence

All Python commands used process-local `APP_ENV=test`, development authentication, a fresh temporary local-storage root, and the existing isolated `clientexplain_e2e` database. Permanent environment files were unchanged.

```powershell
.\.venv\Scripts\python.exe -m pytest services/api/tests/test_authz.py services/api/tests/test_database.py services/api/tests/test_step2_database.py services/api/tests/test_projects.py services/api/tests/test_projects_step2.py services/api/tests/test_storage.py services/api/tests/test_documents_api.py services/api/tests/test_step2_api.py -q
.\.venv\Scripts\python.exe -m pytest services/api/tests -q
npm run test -w apps/web -- src/components/auth-flow.test.tsx 'src/app/api/backend/[...path]/route.test.ts' src/components/project-workspace.test.tsx
npm run test -w apps/web -- src/components/auth-flow.test.tsx
npm test
.\.venv\Scripts\ruff.exe check services/api services/worker
.\.venv\Scripts\ruff.exe format --check services/api services/worker
npm run lint
npm run typecheck
npm run build
```

Exact fresh results:

- Focused backend auth/RLS/project/storage/document/API: **117 passed**.
- Full backend: **357 passed**.
- Focused frontend auth/session/BFF/upload: **60 passed in 3 files**.
- Full Vitest before the targeted fix: **93 passed in 5 files**.
- Targeted logout RED: **2 failed, 24 passed** in `auth-flow.test.tsx` for the expected redirect-race assertions.
- Targeted logout GREEN: **26 passed** in `auth-flow.test.tsx`.
- Full Vitest after the targeted fix: **96 passed in 5 files**.
- Ruff: all checks passed; **67 files** already formatted.
- ESLint: passed.
- TypeScript: passed.
- Production build: passed; **17 application routes/pages** generated/compiled.
- Live Supabase browser verification: **2/2 dedicated accounts** passed login, reload persistence and normal logout; zero page errors. The separate local-development Playwright baseline remains 10/10 and was not substituted for this live evidence.

### Step 2.2 final status — BLOCKED

Step 2.2 is not yet marked PASS. The reproduced explicit-logout defect is fixed and verified, while a fresh live confirmation-code callback remains BLOCKED by hosted Supabase HTTP 429 `over_email_send_rate_limit`. Login, existing-account confirmation metadata, persistence, refresh, logout, backend JWT verification, Account A application upload/download, Account B cross-tenant denial and exact cleanup pass. Only `dashboard-shell.tsx`, `use-session.ts`, their auth tests and these evidence documents changed for the targeted logout fix; no migration, backend authorization, storage policy/configuration, Docker volume or Supabase configuration changed.

Safe next step: wait for the hosted Supabase email-send rate-limit window to reset (or review the project email quota without weakening confirmation), then perform exactly one fresh disposable registration/confirmation callback and reassess Step 2.2 acceptance. Do not start Step 3 while that item remains unresolved.

### Master-plan revalidation and project-deletion race — 2026-11-24

The existing dirty Step 2 working tree was revalidated against the isolated `clientexplain_e2e` database, Redis database 15, private E2E storage and the existing E2E API/worker. The first browser run exposed an orchestration error: the temporary frontend base URL included `/api/v1` even though the BFF appends that prefix, so project calls reached `/api/v1/api/v1/...` and returned 404. Correcting the ignored runner to use the host-only API base allowed the workflows to execute.

That corrected run reproduced a separate application race in desktop and mobile. After a successful project DELETE, `ProjectDetail` removed its still-mounted TanStack project query before navigation. The active query was recreated immediately and issued one GET for the deleted project, producing a real 404 and browser console error. A focused regression test failed with two project reads instead of one. The minimal fix marks the project and activity queries stale with `refetchType: "none"`; it does not refetch while the deleted screen is mounted, while a later direct visit still performs a fresh read.

Fresh RED→GREEN and regression evidence:

- RED: focused project suite **27 passed, 1 failed**; `does not refetch a project after deleting it` observed two reads.
- GREEN: focused project suite **28/28 passed**.
- Full frontend Vitest: **97/97 passed in 5 files**.
- ESLint, TypeScript and the Next.js production build passed; all 17 static pages generated.
- Full isolated Playwright: **10/10 passed** in desktop and mobile Chromium after the fix.
- Full isolated backend Pytest: **357/357 passed**.
- Ruff check/format, Alembic drift, disposable migration audit, `pip check`, production npm audit and Compose validation passed.
- Cleanup: isolated database ended with zero projects, documents and generation jobs; E2E API readiness and worker ping passed.
- Restoration: the normal Supabase production frontend was restored on port 3000. Normal API, worker, watchdog, PostgreSQL and Redis remained running; no database container or volume was restarted or deleted.

This local regression fix does not change the Step 2.2 acceptance decision: the fresh hosted confirmation callback remains BLOCKED by `over_email_send_rate_limit`.

## Isolated E2E stabilization

The isolated browser environment uses database `clientexplain_e2e`, API host port `8001`, Redis database `15`, development authentication, local private E2E storage and disabled external AI processing. Configuration uses the existing variable names `APP_ENV`, `AUTH_MODE`, `NEXT_PUBLIC_AUTH_MODE`, `DEV_AUTH_TOKEN`, `API_INTERNAL_URL`, `DATABASE_URL`, `REDIS_URL`, `STORAGE_BACKEND`, `PRIVATE_STORAGE_ROOT`, and `AI_EXTERNAL_PROCESSING_ALLOWED`; no values or complete connection strings are recorded here.

Root causes resolved during stabilization:

- Health endpoints already existed at `/api/v1/health` and `/api/v1/health/ready`; manual requests to unprefixed `/health` paths correctly returned 404. Docker already probed the canonical readiness path.
- The temporary E2E database password had been interpolated into a SQLAlchemy URL without percent-encoding. A reserved character corrupted the parsed username and caused readiness to return 503. The corrected temporary container configuration uses a percent-encoded password and reaches the isolated database at Alembic head `d14c3a7f2901`.
- Independently launched web, API and worker processes had different development session tokens, producing authenticated frontend sessions followed by backend 401 responses. All isolated components now use one token sourced from the ignored development environment without printing it.
- A fresh development database lacked the fixed development profile/firm/membership required by project foreign keys and RLS. `provision_development_principal()` now transactionally sets both RLS variables before lookup/insertion, serializes first provisioning and idempotently creates the owner workspace. The Supabase branch and `tenant_session()` remain unchanged.
- The Next.js BFF allowlist covered only a subset of frontend-used API paths and omitted `Idempotency-Key`. Its regression table now covers all 14 frontend backend operations plus upload streaming/security behavior.
- The mobile real-workflow test changed its viewport through desktop widths and left it at 1440px before trying to open the mobile navigation. It now restores the original mobile viewport and positively asserts that the mobile navigation control is visible before exercising sign-out; no assertion or workflow was skipped.

Files changed for these fixes and verification:

- `services/api/app/core/auth.py` — idempotent RLS-aware development principal provisioning.
- `services/api/tests/test_authz.py` — repeated development identity/provisioning regression coverage.
- `apps/web/src/app/api/backend/[...path]/route.ts` — method-aware frontend route allowlist and idempotency forwarding.
- `apps/web/src/app/api/backend/[...path]/route.test.ts` — frontend-to-backend route contract coverage.
- `apps/web/e2e/foundation.spec.ts` — restore the initial mobile viewport before the mobile navigation assertion.
- `docs/superpowers/plans/2026-11-23-step-2-e2e-stabilization.md` — execution and review plan.
- `docs/step-2-report.md` — current acceptance evidence.

## Checks executed

| Check | Result / evidence |
|---|---|
| Ruff check and formatting | PASS: 71 Python files formatted; all checks passed |
| Full backend suite | PASS: 357 tests; PostgreSQL/Redis integration included |
| Alembic schema drift | PASS: no new upgrade operations |
| Disposable migration audit | PASS: upgrade, forced RLS, legacy data preservation, recovery-intent and citation rollback guards, downgrade and re-upgrade |
| ESLint / TypeScript | PASS: npm run lint and npm run typecheck |
| Full frontend unit suite | PASS: 93 tests in 5 files |
| Next production build | PASS: Next.js 16.4.6; all 17 static pages generated |
| Production npm dependencies | PASS: npm audit --omit=dev found 0 vulnerabilities |
| Python dependency consistency | PASS: pip check found no broken requirements |
| Clean Docker build | PASS: docker compose --profile app build --no-cache built API, worker and watchdog |
| Docker startup / readiness | PASS: isolated API and worker healthy; `/api/v1/health/ready` reports connected PostgreSQL and Redis; normal Compose services remained healthy and retained their existing uptime |
| Worker ping | PASS: isolated Celery worker returned one node and pong |
| Real generated workflow | PASS: desktop and mobile create project, upload TXT/DOCX/PDF, wait for the real worker, inspect persisted documents, exercise provider-disabled 503, reopen, edit, delete and verify signed-out protection |
| Schema integrity | PASS: zero invalid indexes and zero unvalidated constraints; installed Alembic head d14c3a7f2901 |
| Tracked secret patterns | PASS: no OpenAI/GitHub credential or private-key header matches in tracked files; pattern scan is not a full secret audit |
| Docker logs | Reviewed: API/worker startup successful; database logs contain expected rejected constraint/RLS/lock-timeout and rollback-guard probes from negative tests |
| Fresh Playwright / screenshots | PASS: 10/10 tests in 44.7 seconds across desktop Chromium and mobile Chromium; serious/critical accessibility, responsive widths, error boundaries and real ingestion included |
| PostgreSQL restart persistence | NOT REPEATED in Task 13: preserving concurrently running verification processes; relational persistence/reopen is covered by integration tests |
| GitHub-hosted CI | NOT RUN: workflow updated locally; no hosted CI result claimed |

The final local `scripts/verify.ps1` command includes migration audit, pip check, production npm audit and production build. `-Browser` additionally runs Playwright against already-running web/API/worker services. Fresh stabilization evidence is 357 backend tests, 93 frontend tests and 10 Playwright tests, with all lint/type/schema/migration/dependency/build checks listed below. Rerun after any further code change.

## Stabilization commands executed

All Python test commands used process-local development settings pointed at the isolated database and Redis database; secrets were read without printing and permanent environment files were not edited.

```powershell
.\.venv\Scripts\ruff.exe format --check services scripts
.\.venv\Scripts\ruff.exe check services scripts
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\python.exe -m pytest services/api/tests/test_authz.py -q
.\.venv\Scripts\python.exe -m pytest services/api/tests/test_database.py services/api/tests/test_step2_database.py -q
.\.venv\Scripts\python.exe -m pytest services/api/tests/test_projects.py services/api/tests/test_projects_step2.py services/api/tests/test_documents_api.py services/api/tests/test_step2_api.py -q
.\.venv\Scripts\python.exe -m pytest services/api/tests/test_projects.py::test_health -q
.\.venv\Scripts\alembic.exe -c services/api/alembic.ini check
.\.venv\Scripts\python.exe scripts/audit_migrations.py
.\.venv\Scripts\python.exe -m pip check
npm.cmd run lint
npm.cmd run typecheck
npm.cmd run build
npm.cmd test
npm.cmd run test:e2e
docker compose --profile app config -q
docker exec clientexplain-e2e-worker celery -A worker.celery_app:app inspect ping --timeout 10
```

Exact fresh results:

- Ruff: 71 files formatted; all checks passed.
- Backend: 357 passed. Focused evidence: auth 8 passed; database/RLS 23 passed; projects/documents/workflow 79 passed; health 1 passed.
- Alembic: no new upgrade operations; disposable migration audit passed upgrade, RLS/recovery/downgrade guards, downgrade and re-upgrade.
- Python dependencies: no broken requirements.
- Frontend: ESLint passed; TypeScript passed; production build compiled all 17 routes/pages; Vitest 93 passed in 5 files.
- Playwright: targeted mobile regression 1 passed; complete suite 10 passed in 44.7 seconds.
- Operations: API liveness `ok`; readiness `ready` with database and Redis connected; worker ping `pong`; API and worker healthy.
- Cleanup: isolated E2E database ended with zero projects, documents and generation jobs. Normal API, worker, watchdog, PostgreSQL and Redis containers remained running and healthy and were never restarted or recreated.

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
- **BLOCKED: complete hosted Supabase application Auth and Storage.** Provider JWKS/settings and a private-bucket synthetic lifecycle have been verified, but real registration/confirmation/login/session lifecycle and application-level two-account storage/tenant isolation require two dedicated confirmed accounts and mailbox access.
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
