# Step 2 External Verification Setup Guide

This guide covers the checks that remain external to local Step 2 verification. Do not use real client documents or commit credentials.

## 1. Supabase setup

Create a Supabase project and record:

- Project URL
- Publishable/anon key
- Server-only service-role key
- PostgreSQL connection string, if using hosted PostgreSQL

In the Supabase dashboard:

1. Enable Email authentication.
2. Configure the site URL as `http://localhost:3000` for local testing.
3. Add redirect URL `http://localhost:3000/auth/callback`.
4. Create a private Storage bucket matching `SUPABASE_STORAGE_BUCKET`.
5. Do not enable public bucket access.
6. Configure Storage policies so access is authorized by the server-side application; never expose the service-role key to the browser.
7. Create two test users in separate firms. Do not use production identities.

Set these values in the ignored root `.env`:

```text
AUTH_MODE=supabase
SUPABASE_URL=https://<project-ref>.supabase.co
SUPABASE_PUBLISHABLE_KEY=<publishable-key>
SUPABASE_SERVICE_ROLE_KEY=<server-only-service-role-key>
SUPABASE_STORAGE_BUCKET=<private-bucket-name>
STORAGE_BACKEND=supabase
PRIVATE_STORAGE_ROOT=.local/private-storage
```

Set these in `apps/web/.env.local`:

```text
NEXT_PUBLIC_AUTH_MODE=supabase
NEXT_PUBLIC_SUPABASE_URL=https://<project-ref>.supabase.co
NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY=<publishable-key>
NEXT_PUBLIC_SITE_URL=http://localhost:3000
API_INTERNAL_URL=http://127.0.0.1:8000
```

Restart API, worker and frontend after changing environment variables. Verify that no key appears in logs, bundles, Git status, or committed files.

Expected results:

- Signup creates a user and confirmation email is handled according to the project’s email settings.
- Login creates a persistent browser session.
- Refresh preserves the session.
- Password recovery reaches `/auth/callback`, then reset succeeds.
- A user from Firm A receives `404` or `403` for Firm B projects/documents.
- Private document and generated-object URLs expire and are not publicly accessible.

## 2. OpenAI live verification

Use a dedicated development API key with a low spending limit. Confirm that legal-data processing is approved for the account before sending any content. Use only synthetic text such as:

```text
Synthetic example: A filing is submitted, the opposing party receives notice, and a hearing is scheduled. This is test data, not legal advice.
```

Set in the ignored root `.env`:

```text
AI_EXTERNAL_PROCESSING_ALLOWED=true
OPENAI_API_KEY=<development-key>
OPENAI_ANALYSIS_MODEL=<approved-structured-output-model>
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

Run the provider contract test with the synthetic fixture first. Then perform one live analysis and one live embedding request through the application path. Do not call the provider directly with confidential documents.

Expected results:

- Structured output validates as the existing `LegalProcess` Pydantic schema.
- A real `text-embedding-3-small` response contains 1,536 values per embedding.
- Refusal, timeout, rate-limit and malformed-output handling remains typed and safe.
- No API key, full prompt, source document or access token appears in logs.
- The UI marks generated content as requiring professional lawyer review.

After testing, set `AI_EXTERNAL_PROCESSING_ALLOWED=false` again unless the environment is intentionally retained for development.

## 3. Start the application and run browser checks

From the repository root:

```powershell
docker compose --profile app up -d --wait
npm.cmd run build -w apps/web
npm.cmd run start -w apps/web
```

In a second terminal, verify readiness:

```powershell
Invoke-WebRequest http://127.0.0.1:8000/api/v1/health/ready
Invoke-WebRequest http://127.0.0.1:3000/login
```

Install Chromium if needed and run Playwright:

```powershell
npx playwright install chromium
npm.cmd run test:e2e -w apps/web
```

Run the accessibility checks included by the Playwright suite. Review the generated report:

```powershell
Get-ChildItem apps/web/playwright-report
npx playwright show-report apps/web/playwright-report
```

Test at 375px, 768px, 1024px and 1440px. Expected results:

- Public pages load without console errors.
- Login, recovery, dashboard, project creation, upload, processing, stages and citations work with the configured services.
- No horizontal overflow is present.
- Axe reports no serious or critical violations.
- Failed provider jobs show errors and do not appear successful.

## 4. GitHub Actions

Push the branch to GitHub and open the repository’s Actions tab. The workflow is `.github/workflows/ci.yml`.

If hosted integration tests are enabled, add repository/environment secrets through GitHub Settings, never in YAML:

- `SUPABASE_URL`
- `SUPABASE_PUBLISHABLE_KEY`
- `SUPABASE_SERVICE_ROLE_KEY`
- `SUPABASE_STORAGE_BUCKET`
- `OPENAI_API_KEY` only for an explicitly approved synthetic integration job

Trigger a run by pushing a commit or using **Run workflow** if workflow dispatch is enabled. Do not broaden permissions beyond the workflow’s read-only contents permission.

Expected successful CI results:

- Dependencies install successfully.
- Alembic upgrade and schema audit pass.
- Backend tests, Ruff and dependency checks pass.
- Frontend lint, typecheck, unit tests and production build pass.
- Docker services start and worker ping returns `pong`.
- Playwright completes and uploads its report artifact.

Record the GitHub Actions run URL, commit SHA, conclusion and artifact links in `docs/step-2-report.md`.

## 5. Final acceptance evidence

Step 2 can move from `BLOCKED` to `PASS` only after recording:

- Supabase project URL/configuration (never secret values), test user flow and cross-tenant denial.
- OpenAI model names, synthetic request IDs/timestamps and embedding dimension confirmation.
- Playwright and axe report paths/results for all four viewport sizes.
- PostgreSQL restart/persistence evidence.
- GitHub Actions run URL and successful conclusion.

If any external service is unavailable or a required check fails, keep the Step 2 verdict `BLOCKED` or `FAIL` and document the exact cause.
