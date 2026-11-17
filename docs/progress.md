# Step 1 execution ledger

Plan: docs/superpowers/plans/2026-11-17-foundation.md

- Inspected empty workspace before writing. No working code was replaced.
- Recorded Node 22.12.0 host, Python 3.11.9, Git 2.50.0, Docker 28.5.1, WSL2 Ubuntu, RTX 3050 Laptop 6144 MiB / driver 610.47.
- Ruling: use existing workspace as repository root, standalone PostgreSQL locally, explicit local-only development identity, Supabase JWT integration for hosted accounts. User supplied detailed scope and requested execution without unnecessary approval stops.
- Ruling: no ReactBits dependency added after official docs review; no animation needed for these surfaces.
- Scaffold, dependencies, web pages, API, all 15 application tables, immutable migrations, RLS policies and worker contract implemented.
- First validation test run failed because validation module was absent. Backend integration checks failed before migrations. Both were brought to passing states after implementation/configuration.
- Fixed dependency download timeout by retrying with a longer timeout; fixed Windows PowerShell 5.1 RNG API compatibility.
- Installed project-local Node 22.23.5 to satisfy tools whose minimum exceeds the host Node 22.12.0. npm install under the host may still emit an engine warning; project scripts use the local runtime.
- Fixed initial session-cache redirect after local login; fixed landing title composition.
- Independent review found transaction commit happened too late. Function-scoped dependencies now commit before response; a commit-failure regression test returns 503.
- Readiness now requires the current database revision and projects relation. Full fresh-install commands documented for Windows and WSL/Linux.
- Browser tests corrected to normalize the root canonical URL and await SPA navigation before reloading.
- Automated accessibility checks found low-contrast secondary text. Darkened logo suffix, preview note and workspace callout text.
- Ruff, ESLint and formatting issues resolved. Added httpx2 for current Starlette TestClient, eliminating its compatibility warning.
- Static reviewer confirmed both blocking findings fixed. No remaining blocking review findings; no claim of exhaustive security certification.

Final evidence is recorded in step-1-report.md. Step 2 is not started.

## Completion audit, 18 November 2026

- Revalidated the full frontend, API, migration, PostgreSQL, pgvector, Redis, Celery and Docker foundation.
- Fixed development/Supabase auth-mode consistency, login versus registration password validation, project-detail retry UX and the BFF request-size boundary.
- Removed the redundant legacy httpx dependency and retained the Starlette-compatible httpx2 implementation.
- Added a disposable migration round-trip audit and expanded browser checks to the requested widths, console errors, detail recovery and maximum payload forwarding.
- Confirmed fresh image builds, all four healthy containers, pgvector 0.8.7, Alembic head `c62fbd003112`, zero invalid indexes/unvalidated constraints, Redis PONG and a completed `worker.health` task.
- Final local results: 4 Vitest, 12 Pytest and 10 Playwright tests passed; ESLint, TypeScript, Ruff, formatting, production build, pip dependency check and npm production audit passed.
- Detailed evidence is recorded in `step-1-completion-audit-2026-11-18.md`. Step 2 remains untouched.
