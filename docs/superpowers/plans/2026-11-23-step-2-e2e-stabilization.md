# Step 2 E2E Stabilization Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Verify and stabilize the isolated Step 2 E2E environment without changing normal Supabase services or data.

**Architecture:** Preserve the existing Next.js BFF, prefixed FastAPI routes, PostgreSQL/Redis/Celery workflow, and explicit migrations. Diagnose failures at component boundaries, use the isolated `clientexplain_e2e` database and Redis database 15, and update only regression-covered defects plus the required verification report.

**Tech Stack:** Next.js 16, Playwright, Vitest, FastAPI, SQLAlchemy, PostgreSQL 16/pgvector, Redis, Celery, Alembic, Docker Compose, Ruff.

**Spec:** `C:/Users/adity/.codex/attachments/bd287861-47ba-4044-99a1-db5ed52a7f07/Pasted text.txt`

## Global Constraints

- Preserve Supabase production behavior, normal Docker services, PostgreSQL service, volumes, secrets, and unrelated dirty files.
- Do not weaken security, RLS, validation, authorization, migrations, or tests.
- Do not expose credentials or complete connection strings.
- Stop at Step 2 and report unavailable external verification as BLOCKED.

## Review Focus

- Health probes must exercise the canonical `/api/v1/health/ready` dependency check.
- Development provisioning must be idempotent under RLS and leave Supabase authentication unchanged.
- API, worker, web, database, Redis, storage, and token settings must describe one isolated E2E environment.
- Upload processing must cover TXT, DOCX, and PDF through the real worker.
- Normal Supabase services and data must be unchanged after verification.

---

### Task 1: Establish Baseline and Isolation

**Files:**
- Inspect: `docker-compose.yml`
- Inspect: `services/api/app/api/routes.py`
- Inspect: `apps/web/playwright.config.ts`

- [ ] Record dirty files, architecture, route prefixes, container settings, health state, database name, Redis database, storage root, and token consistency without revealing secrets.
- [ ] Confirm normal services are not targeted by E2E commands.

### Task 2: Run Ordered Static and Backend Verification

**Files:**
- Test: `services/api/tests/`
- Test: `scripts/audit_migrations.py`

- [ ] Run Ruff format/check, full API tests, focused auth/RLS/project/document/health suites, Alembic consistency, migration audit, and dependency checks.
- [ ] For any failure, reproduce narrowly, add a regression test, implement the minimal fix, and rerun relevant suites.

### Task 3: Run Frontend and Browser Verification

**Files:**
- Test: `apps/web/src/**/*.test.*`
- Test: `apps/web/e2e/foundation.spec.ts`

- [ ] Run ESLint, TypeScript, production build, and Vitest.
- [ ] Validate the isolated API/worker/web environment, then run all desktop and mobile Playwright cases without filters or retries.
- [ ] Inspect browser artifacts, console/request failures, and real upload/job behavior.

### Task 4: Operational and End-to-End Verification

**Files:**
- Inspect: `docker-compose.yml`
- Inspect: `packages/contracts/openapi.json`

- [ ] Validate rendered Compose configuration without printing secrets.
- [ ] Verify API readiness, worker ping, isolated database/Redis/storage targeting, project CRUD, document ingestion, provider-disabled response, and cleanup.
- [ ] Confirm normal containers and PostgreSQL service were not modified.

### Task 5: Final Report

**Files:**
- Modify: `docs/step-2-report.md`

- [ ] Record root causes, changed files, commands, exact counts, health behavior, Playwright results, blockers, and one honest PASS/BLOCKED/FAIL status.
- [ ] Review the complete diff and verify no environment or secret file is tracked or changed.
