# Local completion execution record — 2026-11-26

Status: PARTIAL. This record supersedes historical execution boundaries, not historical evidence.

## Scope and rulings

- The current attached request authorizes completing local product features without commits, paid calls, hosted changes, emails, or destructive changes to normal data.
- Older Step 2 email/OpenAI gates remain external blockers but no longer block independent local implementation.
- Preserve the existing `feat/step-2` working tree. At entry README, Next config, session routes, Step 2 report and two plans were modified; the dev-session test and email guide were untracked.
- Use the existing E2E database `clientexplain_e2e`, Redis database 15, and isolated private storage. Normal Compose services were observed healthy and left running.
- Keep existing role names (`owner`, `admin`, `lawyer`, `reviewer`) and tenant models; do not create parallel workflow entities when project/stage/version entities suffice.
- Local auth must use a development frontend. Optimized production builds must reject development auth.

## Inventory and acceptance ledger

Statuses below describe fresh verification, not merely file existence. Historical tests are not current acceptance evidence.

| Feature | Current files / endpoints / data | UI and tests | Status / missing work | Acceptance criteria and dependencies |
|---|---|---|---|---|
| Auth | `core/auth.py`, session routes, `/auth/me`; profiles/firms/members | Auth forms, auth-flow and authz tests | PARTIAL: proxy policy fixed, full integration pending | Dev login/reload/logout; production denial; Supabase transport compatibility; tenant denial |
| Projects | projects API/service/repository; Project | Dashboard/project workspace; project tests | PARTIAL: fresh E2E pending | CRUD persists, authorized deletion, mobile navigation |
| Documents | documents API/service; document and chunk models; worker parsing | Upload/list/details; document pipeline/API tests | PARTIAL: retry/download/preview and UX audit pending | PDF/DOCX/TXT parse, bounded input, provenance, private access, retry and cleanup |
| Analysis / RAG | workflow admission, analysis/RAG/citations services, OpenAI adapter; jobs/chunks/citations | Analysis form/process results; controlled provider tests | PARTIAL: paid-only provider configuration; local provider absent | Actual configured free/local provider, validated output, traceable citations, no fabricated law |
| Workflow editor | ProcessStage and ProjectVersion exist; stage read endpoints | Read-only process results | MISSING | Validated DAG, editable nodes/edges/details, atomic save, reload, conflict handling, mobile |
| Illustrations | worker provider contract; existing image entity | No functional stage UI | MISSING | Clearly labeled deterministic fallback, private stage association, regenerate/delete |
| Lawyer review | Project review status and role model | No review interface | MISSING | Authorized explicit decisions, comments, reviewer identity/history, edit invalidation |
| Exports | Export entity | No export interface | MISSING | Saved-state PDF/PNG, citations/disclaimer/review status, multi-page layout, access checks |
| Account/settings | Profile, account/workspace settings component | Read-only settings | PARTIAL | Functional profile editing and honest available actions |
| Operations | Compose, migrations, readiness, verify scripts | Existing CI and Playwright | PARTIAL | Current regression/build/migrations, safe repeatable startup, desktop/mobile |
| Hosted confirmation/storage | Supabase adapters | Controlled transport tests | BLOCKED | Real email/hosted changes prohibited by current request; retain unverified status |
| Production deployment | Existing deployment notes | No deployment requested | DEFERRED | Separate deployment, TLS, restricted runtime DB roles and operational acceptance |

## Fresh evidence

- Pending dev-session tests: 6 passed.
- Cookie proxy policy regression: RED 2 failed / 19 passed; after shared server policy, full frontend suite GREEN 105 passed in 6 files.
- Fresh Python setup: RED missing APP_ENV; GREEN after environment flag and PostgreSQL port correction.
- Fresh PowerShell setup: RED missing APP_ENV; GREEN; combined setup tests 2 passed. Tests execute in disposable directories and check existing file preservation.
- Full isolated backend and frontend static checks: running; results not yet claimed.

## Next execution steps

1. Finish pending auth, backend, desktop/mobile and production-build acceptance.
2. Finish ingestion lifecycle and provider-independent workflow persistence/editor.
3. Add honest deterministic illustrations, review and saved-state exports.
4. Configure/test a practical local provider if installed resources permit; record any true blocker.
5. Run complete regression, security hardening review, and reconcile this inventory with exact evidence.
