# ClientExplain AI

Legal process project workspace. Step 1 foundation of a four-stage application.

**Available:** responsive public pages, Supabase account integration, explicit local development access, persistent project CRUD, tenant isolation, audit records, migrations, separate Celery worker and automated checks.

**Not yet available:** document upload/processing, OpenAI analysis, retrieval, citations, diffusion generation, diagram editing, lawyer approval, version-history UI and exports. The schema reserves these capabilities; it does not claim they work. All future generated explanations require professional review. Use non-confidential test information in this foundation.

## Windows quickstart

Prerequisites: Docker Desktop running with Linux containers, Python 3.11, Node 22.13+ (22.23.5 recommended), npm and Git. Repository scripts also use a project-local Node 22.23.5 runtime, avoiding the host's older 22.12.0 runtime for builds/tests.

Run in PowerShell from `D:\ClientExplain-Ai`:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements.lock
npm ci
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose up -d --wait postgres redis
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\alembic.exe -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/seed_dev.py
docker compose --profile app up -d --build --wait
npm run dev
```

Open **http://localhost:3000**, choose **Sign in → Open local workspace**. The local identity is explicitly developmental, not a Supabase account. It uses a random HTTP-only session credential; no client records are seeded. API docs: **http://localhost:8000/docs**. Readiness: **http://localhost:8000/api/v1/health/ready**.

`setup.ps1` generates random local database and session credentials in ignored `.env` and `apps/web/.env.local`. Existing environment files are preserved. Do not print, share or commit these files. The public `.env.example` contains no credentials.

For subsequent starts, run `docker compose --profile app up -d --wait` and `npm run dev`. Migrate again when revisions change. For an optimized frontend, run `npm run build` then `npm run start -w apps/web`. Only one web server should use port 3000.

The delivered production frontend runs in the background. To switch to development mode, run `powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-web.ps1` before `npm run dev`. The helper stops only Next.js processes whose command line belongs to this workspace.

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

For API hot reload instead of the API container: stop that container with `docker compose stop api`, then run `.venv\Scripts\python.exe -m uvicorn app.main:app --app-dir services/api --host 127.0.0.1 --port 8000 --reload --no-access-log`. Run Celery in its Linux container, not Windows multiprocessing.

## Verification

With PostgreSQL/Redis running and migrations/seeding complete:

```powershell
.\.venv\Scripts\python.exe -m pytest -q --tb=short
.\.venv\Scripts\ruff.exe check services scripts
.\.venv\Scripts\ruff.exe format --check services scripts
.\.venv\Scripts\alembic.exe -c services/api/alembic.ini check
npm run lint
npm run typecheck
npm test
npm run build
npx playwright install chromium
# Start frontend and API, then:
npm run test:e2e
docker compose --profile app ps
docker compose --profile app exec worker celery -A worker.celery_app:app inspect ping
```

API tests create and remove their own projects. Database policy tests require the local bootstrap database role to create a temporary restricted role, rolled back afterward. Never point these tests at a production database. Playwright drives actual local CRUD, uses only non-confidential generated test names, and deletes successful test projects. Failure artifacts live in ignored `apps/web/test-results` and `apps/web/playwright-report`.

## Supabase configuration

Local development does not require cloud keys. To connect a real Supabase project:

1. Set backend `AUTH_MODE=supabase` and `SUPABASE_URL` in `.env`. Configure asymmetric signing keys supported by the JWKS endpoint (ES256/RS256).
2. Set web `AUTH_MODE=supabase`, `NEXT_PUBLIC_SUPABASE_URL`, and `NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY` in `apps/web/.env.local`. Never put a service-role key in a public variable.
3. Configure allowed site/redirect URLs and email confirmation in Supabase. Restart API and rebuild/restart web.
4. Register, confirm email, then sign in. The verified subject gets a personal workspace on its first API request.

No live Supabase account test is claimed without actual project configuration. Private Storage is reserved for Step 2; no bucket or upload endpoint exists yet. Standalone PostgreSQL has no references to Supabase `auth.users` or `auth.uid()`.

## Structure

```text
apps/web/                  Next.js App Router, components, hooks, services, stores, types
services/api/app/          API, config/auth, models, schemas, repositories, services
services/api/migrations/   Canonical Alembic history
services/api/tests/        Backend and PostgreSQL integration tests
services/worker/           Separate Celery runtime and image provider contract
packages/contracts/       Exported OpenAPI contract
database/                 Migration/seed authority and tenant-policy documentation
infrastructure/           Dockerfiles, monitoring and deployment guidance
docs/                     Architecture, quality checklist and verification results
scripts/                  Local configuration, identity seed, contract export
.github/workflows/         CI lint, type, test, build and browser checks
```

Empty extension directories reserve future modules; their purpose is documented, not hidden behind fake successful endpoints. Exact dependency versions are recorded in `package-lock.json` and `services/api/requirements.lock`.

## Operational notes

- Ports 3000, 8000, 5432 and 6379 bind to loopback. Compose is for local development, not an internet-facing deployment template.
- `docker compose --profile app down` stops services while preserving data volumes. Do not add `-v` unless you intend to delete local data.
- The local database owner can bypass RLS. API tenant predicates are always used, and RLS is independently tested under a restricted role. Production must use a separate restricted runtime role. See `database/policies/README.md`.
- Set the real `NEXT_PUBLIC_SITE_URL` before building for a custom domain. Sitemap, robots and canonical links use that origin.
- The observed GPU is an RTX 3050 Laptop **6 GB**, not 4 GB. No model has been benchmarked or selected, and no large inference dependencies are loaded in FastAPI.
- Production launch requires Supabase verification, restricted database credentials, private storage policy review, retention/backup controls, TLS, rate limits and legal review of the draft policies. See `infrastructure/deployment/README.md`.

Stop at Step 1. Follow `docs/architecture.md` when beginning Step 2.
