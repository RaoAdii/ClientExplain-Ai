# Step 2.2 Live Supabase Verification Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify live Supabase authentication, application-level private storage, and cross-tenant isolation without changing production configuration or touching existing user data.

**Architecture:** Exercise the browser-facing Supabase PKCE flow and same-origin BFF, then verify FastAPI JWT validation, tenant-scoped PostgreSQL access, and server-only Supabase Storage operations. Live mutations are limited to two dedicated non-production accounts and uniquely named synthetic resources, followed by exact cleanup.

**Tech Stack:** Next.js, Supabase Auth JS, FastAPI, PyJWT/JWKS, PostgreSQL RLS, Supabase Storage, Pytest, Vitest, Playwright.

**Spec:** `C:/Users/adity/.codex/attachments/557123c8-1cfc-4e63-9ed2-4f508bc2ca6b/Pasted text.txt`

## Global Constraints

- Do not expose secrets, weaken RLS or authorization, make storage public, or modify existing accounts/data.
- Use only two dedicated non-production accounts and synthetic resources for live mutations.
- Preserve ignored environment files, Docker databases/volumes, and all uncommitted changes.
- Do not start Step 3 or automatically commit changes.

## Review Focus

- Missing dedicated credentials or mailbox access must produce BLOCKED, never simulated PASS.
- Callback `next` input must not permit an external redirect.
- Account B must receive no metadata, storage key, content, or signed URL for Account A resources.
- Cleanup must target only exact synthetic IDs/keys created by this verification.
- Browser bundles and logs must not expose backend-only service credentials or bearer tokens.

---

### Task 1: Map implementation and safe test prerequisites

**Files:**
- Inspect: `apps/web/src/lib/supabase.ts`
- Inspect: `apps/web/src/components/auth-form.tsx`
- Inspect: `apps/web/src/components/password-recovery.tsx`
- Inspect: `apps/web/src/hooks/use-session.ts`
- Inspect: `apps/web/src/app/api/backend/[...path]/route.ts`
- Inspect: `services/api/app/core/auth.py`
- Inspect: `services/api/app/services/documents.py`
- Inspect: `services/api/app/integrations/storage.py`
- Inspect: `services/api/migrations/versions/c62fbd003112_tenant_policies.py`

**Interfaces:**
- Consumes: permanent environment variable names without revealing values.
- Produces: an exact flow map and a go/no-go decision for live account tests.

- [x] Verify auth/storage modes and backend/frontend Supabase configuration consistency without printing values.
- [x] Verify two dedicated account credentials and mailbox access are available through an existing secure mechanism.
- [x] Stop live account mutations and record BLOCKED if either dedicated account prerequisite is absent.

**Resume evidence (2026-11-24):** Supabase auth/storage modes and backend/frontend project configuration remain consistent. All four required values are present in the ignored `.env.step22.local`; the two email identities are distinct, and both authenticate as confirmed, independent Supabase subjects. The prerequisite gate passed without printing values.

### Task 2: Verify safe static and controlled security behavior

**Files:**
- Test: `services/api/tests/test_authz.py`
- Test: `services/api/tests/test_storage.py`
- Test: `services/api/tests/test_documents_api.py`
- Test: `apps/web/src/components/auth-flow.test.tsx`
- Test: `apps/web/src/app/api/backend/[...path]/route.test.ts`

**Interfaces:**
- Consumes: implementation flow from Task 1.
- Produces: evidence for JWT validation, callback validation, BFF restrictions, upload validation, storage-key safety, and tenant checks.

- [x] Audit frontend source/build inputs for service-role exposure and unsafe redirect handling.
- [x] Run focused backend and frontend auth/storage/BFF suites.
- [ ] If a defect is reproduced, add a failing regression test before the smallest application fix.

### Task 3: Exercise live two-account application flow when prerequisites exist

**Files:**
- Modify only if a defect is proven: owning application file and focused regression test.

**Interfaces:**
- Consumes: two dedicated confirmed accounts from Task 1.
- Produces: registration, confirmation, login, refresh, logout, backend identity, cross-tenant, application upload/download, and cleanup evidence.

- [ ] Exercise registration, confirmation callback, duplicate registration, valid/invalid login, refresh, expiry, and logout through the application.
- [x] Create one uniquely named synthetic Account A project/document through the BFF and verify authorized metadata/download.
- [x] Attempt every Account A identifier using Account B and anonymously; require non-disclosing rejection.
- [x] Delete only the exact synthetic document/project and verify database/storage cleanup through supported application behavior.

**Live execution evidence (2026-11-24):** Both accounts passed password login, provider user validation, backend JWT identity, stable repeated identity, token refresh and provider logout/revoked-refresh checks. Account A created one uniquely named synthetic project, uploaded one synthetic TXT file, received a 300-second authorized signed download, deleted the document and project, and left zero exact database rows/jobs and no storage object. Account B received six non-disclosing HTTP 404 denials; anonymous application requests received HTTP 401; direct Account B and anonymous storage reads were denied. Explicit browser logout reproduced a defect: the application reached `/login?reason=session-expired` instead of normal `/login`. Execution stopped before a fix as required.

**Targeted TDD fix evidence (2026-11-24):** Three regression tests were added around the existing unexpected-expiration test. RED reproduced one erroneous expiration redirect for a normal logout and two for repeated `SIGNED_OUT` events. The minimal fix passes an explicit-logout intent ref from `DashboardShell` to `useSession`; the SDK event continues clearing private state but does not emit expiration messaging/navigation during a user-initiated logout, and failed logout resets the intent. GREEN: focused auth 26/26, complete Vitest 96/96, ESLint, TypeScript and production build passed. Live browser login, reload persistence and logout to clean `/login` passed for both dedicated accounts with zero page errors.

**Fresh callback attempt (2026-11-24):** A disposable Gmail plus-alias was generated from the user-selected Primary mailbox and submitted through the real `/register` page in a browser retaining its PKCE state. The first harness attempt was rejected with HTTP 400 `validation_failed` because its generated password was 73 characters; the harness was corrected to a provider-compatible length without application changes. The corrected real signup was then rejected by hosted Supabase with HTTP 429 `over_email_send_rate_limit` before any confirmation email or callback. Execution stopped without retrying. Cleanup audit found zero matching disposable Supabase users and zero remaining mailbox/callback/cleanup IPC files. Registration, fresh confirmation email, real callback exchange and resulting session were therefore not verified in this attempt.

**Email-delivery investigation (2026-11-24):** No email-sending Auth endpoint was called. Public hosted settings confirm email signups remain enabled and auto-confirm remains disabled, but do not expose SMTP selection, configured email limits, remaining quota or Auth logs. No Supabase Management API credential is available locally. Official documentation identifies the built-in service limit as 2 Auth emails per project per hour and documents `over_email_send_rate_limit` for exhaustion. The observed state is consistent with the built-in provider but cannot be management-confirmed. By 16:47 IST roughly 91 minutes had elapsed since the recorded 429, but elapsed time cannot prove the shared project quota is unused or confirm the provider configuration. With no non-sending remaining-quota endpoint, the one fresh registration attempt was preserved. `docs/supabase-auth-email-delivery.md` records the approval-gated Dashboard/Management inspection and custom SMTP procedure.

### Task 4: Regression gate and report

**Files:**
- Modify: `docs/step-2-report.md`

**Interfaces:**
- Consumes: exact outputs from Tasks 1–3.
- Produces: auditable Step 2.2 PASS/BLOCKED/FAIL/NOT TESTED status.

- [x] Run the required backend, Vitest, ESLint, TypeScript, production build, and Playwright suites when changes or executable live prerequisites warrant the full gate.
- [x] Record exact counts, live-vs-controlled evidence, cleanup, root causes, changed files, and remaining blockers without identifiers or secrets.
- [ ] Mark Step 2.2 PASS only if every acceptance criterion was verified with the two dedicated accounts.
