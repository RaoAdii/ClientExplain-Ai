# Final Demo Guide

## What this demo shows

This is a local, provider-disabled MVP demonstration. It shows a synthetic text upload being parsed, a person building and saving a workflow, and the saved workflow being downloaded as a PDF report and PNG diagram. Analysis is intentionally unavailable unless a provider is configured and approved; the demo does not invent stages, citations, or legal conclusions.

The sample is entirely fictional: [demo-fictitious-community-venue-process.txt](../samples/demo-fictitious-community-venue-process.txt). It describes no real venue, agreement, organization, rule, deadline, legal process, or person.

## Start locally on Windows

Use PowerShell from the repository root. Required software: Docker Desktop with Linux containers, Python 3.11, npm, and Git. The repository's local Node runtime is used by npm scripts.

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r services/api/requirements.lock
npm ci
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
```

`setup.ps1` creates ignored local environment files only when they are missing. It does not replace existing settings. Check the development-token pair without printing either value, then set process-only local overrides:

```powershell
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
```

These process-level settings override stale hosted modes without changing `.env` or `apps/web/.env.local`. Keep this PowerShell session open for the following commands:

```powershell
docker compose up -d --wait postgres redis
$env:PYTHONPATH = 'services/api'
.\.venv\Scripts\alembic.exe -c services/api/alembic.ini upgrade head
.\.venv\Scripts\python.exe scripts/seed_dev.py
docker compose --profile app up -d --build --wait
Invoke-RestMethod http://127.0.0.1:8000/api/v1/health/ready
npm run dev
```

Open **http://127.0.0.1:3000**, select **Sign in → Open local workspace**. Do not copy or print either ignored environment file. Do not use real or confidential documents. Do not run `docker compose down -v`; it deletes persistent data.

For later sessions, repeat the token check and process-level overrides before starting the Compose app and web server. The Compose environment accepts these overrides so local auth/storage and the disabled AI gate take precedence over values in the preserved `.env`.

## Run the demo

1. Create a project such as **Fictional Venue Request**.
2. Upload `samples/demo-fictitious-community-venue-process.txt`. Wait until its status is **Ready for analysis**.
3. Do not submit analysis. The UI should show that AI analysis is not configured and keep the submission button disabled. This is expected.
4. Open **Visual workflow → Open workflow editor**. Add stages based on the sample, edit their explanations, and connect them. These are manual, user-authored stages—not AI output.
5. Save the workflow. PDF/PNG exports are enabled only when the workflow is saved and unchanged.
6. Download **workflow PNG** and **workflow PDF**. The PNG is a locally generated SVG-derived stage/connection diagram, explicitly not AI-generated or legally verified. The PDF is a text report of saved stages, connections, workflow version, and review-status metadata; it does not include the diagram. Both are generated in the browser and are not persisted by the API.
7. Review the on-screen notice and the `requires review` state. An export or status value is not professional approval or legal advice.

The PDF supports printable Latin-1 text. It rejects unsupported scripts and control characters instead of silently substituting text; the diagram export remains available.

## Clean up after the demo

Delete the uploaded document from the project before deleting the project. Document deletion removes its private local file; project deletion alone may leave local document files behind. The browser acceptance test follows this order and removes its generated project.

## If readiness is unavailable

Check `docker compose --profile app ps`, confirm PostgreSQL and Redis are healthy, apply the current Alembic head with the command above, and rebuild the app containers with `docker compose --profile app up -d --build --wait`. Do not reset the database or remove volumes to resolve a readiness issue.
