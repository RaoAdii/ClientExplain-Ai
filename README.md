# ClientExplain AI

A legal-process workspace for turning source documents into structured, reviewable workflows.

> **Project status:** Step 2 MVP; ready for a local demonstration, not production-ready or a live AI demonstration.

## What works

- Local development sign-in and tenant-scoped project/profile management.
- Private PDF, DOCX, and UTF-8 TXT uploads, asynchronous parsing, status reporting, retry for failed documents, and audit records.
- Editable workflow stages and connections with save, reload, and conflict handling.
- Browser-generated PDF reports and PNG workflow diagrams based on saved workflow data.
- OpenAI and Ollama analysis adapters, embeddings, retrieval, and citation publication, tested with controlled transports.

The demonstrated journey is deliberately local: upload a fictional sample, manually create and save a workflow, then export it. When AI is unavailable, the application blocks analysis rather than fabricating stages or citations. Real Ollama inference, live OpenAI generation, and hosted Supabase Auth/Storage have not been verified.

## Not included in the current demo

- Stage-specific illustrations, version-history UI, and substantive lawyer-review history.
- Evidence that a workflow's review-status field represents professional approval.
- Legal validation or advice. Every generated explanation requires review by a qualified professional.

PDF exports support printable Latin-1 text; unsupported scripts are rejected instead of silently altered. Use only non-confidential, fictional fixtures locally. See the [local demo guide](docs/FINAL_DEMO_GUIDE.md), [verified project status](docs/FINAL_PROJECT_STATUS.md), and [Step 2 verification report](docs/step-2-report.md).

## Windows quickstart

Prerequisites: Docker Desktop running with Linux containers, Python 3.11, Node 22.13+ (22.23.5 recommended), npm and Git. Repository scripts also use a project-local Node 22.23.5 runtime, avoiding the host's older 22.12.0 runtime for builds/tests.

Run in PowerShell from `D:\ClientExplain-Ai`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements.lock
npm ci
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
$backendTokenLine = Get-Content .env | Where-Object { $_ -match '^DEV_AUTH_TOKEN=' } | Select-Object -First 1
$webTokenLine = Get-Content apps/web/.env.local | Where-Object { $_ -match '^DEV_AUTH_TOKEN=' } | Select-Object -First 1
if (-not $backendTokenLine -or -not $webTokenLine) { throw 'Local development token is missing.' }
$backendToken = $backendTokenLine.Substring('DEV_AUTH_TOKEN='.Length)
$webToken = $webTokenLine.Substring('DEV_AUTH_TOKEN='.Length)
if ($backendToken -cne $webToken) { throw 'Local development tokens do not match; preserve the files and reconcile them before continuing.' }
$env:DEV_AUTH_TOKEN = $backendToken
$env:APP_ENV = 'development'
$env:AUTH_MODE = 'development'
$env:NEXT_PUBLIC_AUTH_MODE = 'development'
$env:API_INTERNAL_URL = 'http://127.0.0.1:8000'
$env:STORAGE_BACKEND = 'local'
$env:AI_EXTERNAL_PROCESSING_ALLOWED = 'false'
$env:AI_PROVIDER = 'openai'
docker compose up -d --wait postgres redis
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\alembic.exe -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/seed_dev.py
docker compose --profile app up -d --build --wait
npm run dev
```

Open **http://localhost:3000**, choose **Sign in → Open local workspace**. The local identity is explicitly developmental, not a Supabase account. It uses a random HTTP-only session credential; no client records are seeded. API docs: **http://localhost:8000/docs**. Readiness: **http://localhost:8000/api/v1/health/ready**.

`setup.ps1` generates random local database and session credentials in ignored `.env` and `apps/web/.env.local`. Existing environment files are preserved. Do not print, share or commit these files. The public `.env.example` contains no credentials.

For subsequent local starts, re-run the process-level setup above (including the non-displaying token match check), then run `docker compose --profile app up -d --wait` and `npm run dev`. This selects local authentication/storage and disables external AI without changing existing ignored environment files. Migrate again when revisions change. For an optimized frontend, run `npm run build` then `npm run start -w apps/web`. Only one web server should use port 3000.

If port 3000 is occupied by a Next.js process from this workspace, `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-web.ps1` stops only matching workspace-owned Next.js processes. Do not stop unrelated processes.

## WSL2 / Linux

Enable Docker Desktop integration for Ubuntu. Prefer a checkout in the Linux filesystem rather than sharing Windows node_modules or .venv.

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r services/api/requirements.lock
npm ci
python scripts/configure.py
docker compose up -d --wait postgres redis
export PYTHONPATH=services/api
alembic -c services/api/alembic.ini upgrade head
python scripts/seed_dev.py
docker compose --profile app up -d --build --wait
npm run dev
```

For API hot reload instead of the API container: stop that container with `docker compose stop api`, then run `python -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload --no-access-log`. Run Celery in its Linux container, not Windows multiprocessing.

## Verification

With PostgreSQL/Redis running and migrations/seeding complete:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
# Start frontend and Docker API/worker before browser checks:
npx playwright install chromium
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1 -Browser
docker compose --profile app ps
docker compose --profile app exec worker celery -A worker.celery_app:app inspect ping
```

API tests create and remove their own projects. Database policy tests require the local bootstrap database role to create a temporary restricted role, rolled back afterward. Never point these tests at a production database. Playwright drives actual local CRUD, PDF/DOCX/TXT ingestion and the expected provider-disabled response, uses only non-confidential generated test names, and deletes successful test projects. Failure artifacts live in ignored `apps/web/test-results` and `apps/web/playwright-report`.

## Supabase configuration

Local development does not require cloud keys. To connect a real Supabase project:

1. Set backend `AUTH_MODE=supabase` and `SUPABASE_URL` in `.env`. Configure asymmetric signing keys supported by the JWKS endpoint (ES256/RS256).
2. Set web `AUTH_MODE=supabase`, `NEXT_PUBLIC_AUTH_MODE=supabase`, `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` in `apps/web/.env.local`. The public and server auth modes must match. Never put a service-role key in a public variable.
3. Configure allowed site/redirect URLs and email confirmation in Supabase. Restart API and rebuild/restart web.
4. Register, confirm email, then sign in. The verified subject gets a personal workspace on its first API request.

No live Supabase account test is claimed without actual project configuration. For hosted private document storage also set backend `STORAGE_BACKEND=supabase`, `SUPABASE_STORAGE_BUCKET` and `SUPABASE_SERVICE_ROLE_KEY`. The adapter rejects public buckets; keep the service key server-only. Local storage is prohibited in production. Hosted storage behavior is covered by controlled HTTP transport tests, with live bucket/policy verification still blocked. Standalone PostgreSQL has no references to Supabase `auth.users` or `auth.uid()`.

## Structure

```text
apps/web/                  Next.js App Router, components, hooks, services, stores, types
services/api/app/          API, config/auth, models, schemas, repositories, services
services/api/migrations/   Canonical Alembic history
services/api/tests/        Backend and PostgreSQL integration tests
services/worker/           Separate Celery runtime and image provider contract
packages/contracts/        Exported OpenAPI contract
database/                 Migration/seed authority and tenant-policy documentation
infrastructure/           Dockerfiles, monitoring and deployment guidance
docs/                     Architecture, quality checklist and verification results
samples/                   Fictional, non-confidential demo fixtures
scripts/                  Local configuration, identity seed, contract export
.github/workflows/         CI lint, type, test, build and browser checks
```

Exact dependency versions are recorded in `package-lock.json` and `services/api/requirements.lock`.

## Operational notes

- Ports 3000, 8000, 5432 and 6379 bind to loopback. Compose is for local development, not an internet-facing deployment template.
- `docker compose --profile app down` stops services while preserving data volumes. Do not add `-v` unless you intend to delete local data.
- The local database owner can bypass RLS. API tenant predicates are always used, and RLS is independently tested under a restricted role. Production must use a separate restricted runtime role. See `database/policies/README.md`.
- Set the real `NEXT_PUBLIC_SITE_URL` before building for a custom domain. Sitemap, robots and canonical links use that origin.
- Production launch requires Supabase verification, restricted database credentials, private storage policy review, retention/backup controls, TLS, rate limits and legal review of the draft policies. See `infrastructure/deployment/README.md`.

This repository documents the Step 2 implementation boundary and remaining external verification in [architecture](docs/architecture.md) and the [verification report](docs/step-2-report.md).

## Step 2 workflow and AI configuration

Create a project and enter jurisdiction, legal area, language and audience. Upload one matching PDF, DOCX or UTF-8 TXT file at a time (maximum 25 MiB). The worker parses privately stored documents and persists ordered chunks with source metadata; the UI shows document status, page count, and parsing errors, but does not provide a document-text/chunk preview. Manually build and save a workflow without an AI provider, then export its saved stages and connections as a PDF report or locally generated PNG diagram. These exports do not validate the content or constitute legal advice. Delete documents individually before deleting a project so local files are removed. Redis rate limits uploads and analysis per tenant/user; duplicate content is rejected within a project.

For OpenAI, analysis requires ready documents or process text, request-level consent, backend `AI_EXTERNAL_PROCESSING_ALLOWED=true`, `OPENAI_API_KEY` and an explicit `OPENAI_ANALYSIS_MODEL`. Keep the gate disabled until external processing is approved. For local Ollama, set `AI_PROVIDER=ollama`, `OLLAMA_BASE_URL` (the Docker default is `http://host.docker.internal:11434`), `OLLAMA_ANALYSIS_MODEL` and `OLLAMA_EMBEDDING_MODEL`; both models must be installed. The API restricts Ollama endpoints to local addresses and reports availability at `GET /api/v1/ai/status`. Embeddings must be exactly 1536 dimensions to match pgvector; vectors are never padded. Real Ollama inference has not yet been verified. No paid AI calls were made.

The API and worker share a private named volume at `/var/lib/clientexplain/private-storage`; their unprivileged users have the same UID. The watchdog reconciles interrupted terminal job writes. Readiness checks database, Redis and Alembic head `f4a8d1c7e902`. Schema changes run explicitly using Alembic before starting the application images; they never run implicitly on API startup.
