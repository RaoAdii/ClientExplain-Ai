# Step 1 implementation plan

Goal: deliver a locally runnable foundation without presenting future AI capabilities as implemented.

Architecture and spec: ../../architecture.md and the user's Step 1 specification. Build in the provided empty workspace. User explicitly requested execution in order; do not introduce extra design approval gates.

## Tasks

- [x] Inspect workspace, versions, GPU and official component documentation.
- [x] Record architecture, tenant boundaries, local auth and inference decisions.
- [x] Scaffold web, API, worker and infrastructure directories and dependencies.
- [x] Implement all 15 tables, Alembic revision, tenant constraints and policies.
- [x] Implement health/readiness, validated project CRUD, auth and error handling.
- [x] Implement public pages, auth, responsive dashboard, real CRUD and settings.
- [x] Run migrations and launch PostgreSQL, Redis, API, worker and web.
- [x] Verify API persistence, unauthenticated rejection, tenant isolation and validation with Pytest.
- [x] Verify form validation with Vitest and browser flows/responsiveness with Playwright.
- [x] Run Ruff, ESLint, type checks and production build; correct failures.
- [x] Review code, publish evidence and global checklist, stop after Step 1.

Review focus: missing cloud credentials must not yield fake authentication; tenant identifiers cannot be chosen by callers; whitespace-only names must fail; unavailable infrastructure must yield useful errors; narrow viewports and keyboard navigation must retain every action.
