# ClientExplain AI Completion Master Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Complete ClientExplain AI as a secure, polished LegalTech SaaS while preserving existing behavior, data, uncommitted work, and evidence gates.

**Architecture:** Extend the existing Next.js/FastAPI/PostgreSQL/Redis/Celery modular monolith. Deliver each major subsystem through its own detailed TDD plan, with live external integrations gated separately from controlled tests and with one final cross-system acceptance suite.

**Tech Stack:** Next.js App Router, React, TypeScript, Tailwind CSS, TanStack Query, Zustand, React Hook Form, Zod, React Flow, FastAPI, Pydantic, SQLAlchemy, Alembic, PostgreSQL/pgvector, Redis, Celery, Supabase, OpenAI, Docker Compose, GitHub Actions.

**Spec:** `C:/Users/adity/.codex/attachments/1d883ed4-b17c-4c34-9d73-6ff1e85dcd24/Pasted text.txt`

## Global Constraints

- Preserve all existing uncommitted work; do not create commits unless explicitly authorized.
- Never delete existing data, reset Docker volumes, weaken RLS/authorization, expose secrets, or use confidential legal material for verification.
- Do not start Step 2.3 until every Step 2.2 acceptance criterion has real evidence.
- Do not make paid provider calls or deploy publicly without explicit approval.
- Use TDD for reproducible defects and run focused checks before broader regression gates.
- A mandatory criterion is never PASS when it is blocked, failed, unimplemented, or not verified.

## Review Focus

- Cross-tenant identifiers, storage keys, signed URLs, jobs, stages, and citations must remain non-disclosing under every new feature.
- Retryable background work must be idempotent across duplicate delivery, worker interruption, and stale completion.
- Legal outputs must preserve provenance and must not invent jurisdiction-specific law, deadlines, or citations.
- Large documents/workflows and 320px mobile layouts must remain usable without unbounded memory, overflow, or inaccessible controls.
- Exported and generated artifacts must inherit private authorization, cleanup, retention, and professional-review requirements.

---

### Task 1: Preserve and revalidate the existing Step 2 working tree

**Files:**
- Inspect: all files reported by `git status --short`
- Test: existing backend, frontend, E2E, migration, dependency, and Docker checks
- Modify: `docs/step-2-report.md` only when new evidence exists

**Interfaces:**
- Consumes: the existing dirty auth/BFF/E2E/logout/Compose changes.
- Produces: a stable, evidence-backed base for subsequent work.

- [x] Run focused regression tests for each dirty implementation area.
- [x] Run the complete local verification suite against the documented isolated test targets.
- [x] Reconcile test counts and failures with `docs/step-2-report.md` without erasing historical evidence.

**Execution evidence (2026-11-24):** Focused authentication passed 8/8 and focused auth/BFF passed 45/45. Full isolated backend passed 357/357. A corrected isolated browser run exposed an active-query refetch after project deletion; RED was 27 passed/1 failed, GREEN was 28/28, full Vitest passed 97/97, and the final Playwright run passed 10/10. Ruff, ESLint, TypeScript, production build, Alembic drift, disposable migration audit, dependency checks and Compose validation passed. The E2E database ended with zero projects/documents/jobs and the Supabase production frontend was restored.

### Task 2: Complete the Step 2.2 live confirmation gate

**Files:**
- Follow: `docs/superpowers/plans/2026-11-24-step-2-2-live-supabase-verification.md`
- Modify: `docs/step-2-report.md`
- Modify: the Step 2.2 plan only with actual evidence

**Interfaces:**
- Consumes: one fresh disposable non-production mailbox after the Supabase email rate-limit window resets.
- Produces: real registration, confirmation callback, session persistence, logout, and exact cleanup evidence.

- [ ] Confirm the hosted email-send rate-limit window or quota permits one fresh attempt without changing security settings.
- [ ] Register through the real application and complete the fresh PKCE confirmation callback.
- [ ] Verify intended route, backend identity, reload persistence, normal logout, and exact cleanup.
- [ ] Mark Step 2.2 PASS only when every criterion has evidence; otherwise retain BLOCKED/FAIL.

### Task 3: Plan and verify Step 2.3 OpenAI integration

**Files:**
- Inspect: `services/api/app/integrations/openai_provider.py`
- Inspect: `services/api/app/services/{analysis,rag,prompting,citations}.py`
- Inspect: `services/worker/pipelines/analysis.py`
- Test: existing analysis/provider/RAG suites plus a separately approved live test

**Interfaces:**
- Consumes: Step 2.2 PASS and explicit approval for the named model, estimated cost, and synthetic request.
- Produces: live structured-output, embedding, retrieval, citation, usage, latency, and error evidence.

- [ ] Write a dedicated Step 2.3 design and TDD execution plan after the gate opens.
- [ ] Audit model compatibility, pricing, schema support, dimensions, timeouts, retries, rate limits, and data controls.
- [ ] Obtain explicit approval before the minimum live paid verification.
- [ ] Verify with synthetic legal text and record actual usage/cost without exposing keys or payload secrets.

### Task 4: Complete project, account, and ingestion lifecycle gaps

**Files:**
- Modify: project/account API, schema, service, repository, component, and test files selected by the detailed design
- Create: migrations only for legitimate persisted state required by the approved design

**Interfaces:**
- Consumes: the current project/document ownership and audit contracts.
- Produces: approved duplicate/archive/profile/account-deletion and ingestion retry behavior.

- [ ] Design the precise lifecycle semantics and retention rules before implementation.
- [ ] Add failing authorization, idempotency, cleanup, and UI tests for each approved operation.
- [ ] Implement the smallest typed API/UI changes and migration, if required.
- [ ] Verify cross-tenant denial, cascades, background-job cancellation, and exact storage cleanup.

### Task 5: Build the editable visual workflow

**Files:**
- Modify/Create: focused React Flow editor, stage panel, layout persistence, API contracts, services, models/migration, and tests defined by its detailed plan

**Interfaces:**
- Consumes: ordered persisted stages and source/citation contracts.
- Produces: accessible editable nodes/edges, saved layouts, and deterministic restoration for export.

- [ ] Write and approve a workflow-editor design covering desktop, 320–768px layouts, keyboard behavior, large graphs, and persistence conflicts.
- [ ] Implement RED→GREEN API and component tests for stage edits, edges, positions, save/restore, authorization, and concurrency.
- [ ] Add focused Playwright coverage for editing, reopening, mobile adaptation, and keyboard access.

### Task 6: Implement real image generation through the worker

**Files:**
- Modify/Create: worker provider, task/pipeline, status/storage APIs, UI controls, and tests defined by its detailed plan

**Interfaces:**
- Consumes: approved provider/model, stage content, private storage, durable jobs.
- Produces: per-stage private illustrations with status, retry, regeneration, cleanup, and export references.

- [ ] Benchmark/select a provider compatible with policy, licensing, cost, and the RTX 3050 6GB constraint.
- [ ] Obtain approval for any paid call or new heavyweight dependency.
- [ ] TDD idempotency, authorization, prompt safety, retries, cancellation, storage privacy, and cleanup.
- [ ] Verify an actual configured provider separately from mocks; retain NOT VERIFIED until live evidence exists.

### Task 7: Implement verified PDF and PNG export

**Files:**
- Modify/Create: export service/route, renderer, UI, artifact authorization/cleanup, and tests defined by its detailed plan

**Interfaces:**
- Consumes: saved workflow layout, citations, project metadata, private images, branding, disclaimer.
- Produces: downloadable PDF/PNG artifacts with deterministic layout and private access.

- [ ] Approve an export architecture after measuring browser/server rendering tradeoffs.
- [ ] TDD authorization, page breaks, large workflows, citation inclusion, failures, cleanup, and accessibility of the export UI.
- [ ] Inspect generated file contents and dimensions; button existence is not acceptance evidence.

### Task 8: Perform the product-wide UI/UX and accessibility pass

**Files:**
- Modify: existing pages/components/styles and focused tests; do not replace functional architecture for appearance alone

**Interfaces:**
- Consumes: completed functional surfaces from Tasks 4–7.
- Produces: consistent LegalTech visual system, responsive behavior, accessible interactions, and honest product copy.

- [ ] Create and approve a page-by-page design specification grounded in current screenshots and real states.
- [ ] Audit landing, auth, dashboard, project, workflow, settings, errors, legal pages, and navigation at specified widths.
- [ ] TDD navigation, focus, dialogs, reduced motion, contrast, semantics, overflow, and touch behavior.
- [ ] Capture current desktop/mobile evidence without fake metrics, claims, logos, testimonials, or inert controls.

### Task 9: Complete security, privacy, and reliability review

**Files:**
- Modify: only findings supported by a reproduction/test
- Create/Modify: threat model, security evidence, operations documentation

**Interfaces:**
- Consumes: the complete product attack surface and deployment design.
- Produces: triaged findings, verified fixes, residual risks, and confidential-document threat model.

- [ ] Review authentication, authorization, RLS, BFF, storage, uploads, jobs, exports, XSS/CSRF, SSRF, rate limits, logging, dependencies, and secrets.
- [ ] Reproduce every actionable defect before a focused TDD fix.
- [ ] Verify restricted runtime database roles, migration paths, retries, idempotency, readiness, and recovery.
- [ ] Record unresolved critical/important findings as FAIL; never waive them silently.

### Task 10: Run full regression, deployment readiness, and final acceptance

**Files:**
- Modify: README, architecture, environment, troubleshooting, deployment, backup/restore, monitoring, incident-response, and final report documentation

**Interfaces:**
- Consumes: all prior tasks and external integration evidence.
- Produces: an auditable release decision and startup/deployment instructions.

- [ ] Run Ruff format/check, full Pytest, migration audit, Vitest, ESLint, TypeScript, production build, Playwright, dependency scans, Compose validation, readiness, and worker ping.
- [ ] Verify clean and current database migration paths without deleting existing volumes or data.
- [ ] Validate metadata, sitemap, robots, canonical URLs, legal drafts/disclaimer, custom 404, and documentation.
- [ ] Produce the required final report with exact commands, counts, exit codes, modified files, Git status, blockers, startup, and deployment instructions.
- [ ] Use PASS/BLOCKED/FAIL/NOT IMPLEMENTED/NOT VERIFIED per criterion; never collapse unresolved mandatory criteria into an overall PASS.
