# Local completion execution record — 2026-11-26

Status: PARTIAL. This record supersedes historical execution boundaries, not historical evidence.

## Scope and rulings

- The current attached request authorizes completing local product features without commits, paid calls, hosted changes, emails, or destructive changes to normal data.
- Older Step 2 email/OpenAI gates remain external blockers but no longer block independent local implementation.
- Preserve the existing `feat/step-2` working tree. At entry README, Next config, session routes, Step 2 report and two plans were modified; the dev-session test and email guide were untracked.
- Use the existing E2E database `clientexplain_e2e`, a dedicated Redis database, and isolated private storage. Normal Compose services and volumes must be preserved.
- Keep existing role names (`owner`, `admin`, `lawyer`, `reviewer`) and tenant models; do not create parallel workflow entities when project/stage/version entities suffice.
- Local auth must use a development frontend. Optimized production builds must reject development auth.

## Inventory and acceptance ledger

Statuses below describe fresh verification, not merely file existence. Historical tests are not current acceptance evidence.

| Feature | Current files / endpoints / data | UI and tests | Status / missing work | Acceptance criteria and dependencies |
|---|---|---|---|---|
| Auth | `core/auth.py`, session routes, `GET/PATCH /auth/me`; profiles/firms/members | Auth forms, profile editor, auth-flow and authz tests | PARTIAL: local auth and profile editing implemented; hosted Supabase acceptance pending | Dev login/reload/logout; production denial; hosted session and tenant checks |
| Projects | projects API/service/repository; Project | Dashboard/project workspace; project tests | PARTIAL: fresh E2E pending | CRUD persists, authorized deletion, mobile navigation |
| Documents | documents API/service; document and chunk models; worker parsing; retry endpoint | Upload/list/details/retry; document pipeline/API tests | PARTIAL: retry implemented; download/preview and storage cleanup on project deletion remain | PDF/DOCX/TXT parse, bounded input, provenance, private access, retry and exact cleanup |
| Analysis / RAG | workflow admission, analysis/RAG/citations services, OpenAI and Ollama adapters; jobs/chunks/citations | Analysis form/provider status; controlled provider tests | PARTIAL: Ollama runtime/model execution unverified; live OpenAI remains gated | Available provider, validated output, traceable citations, no fabricated law |
| Workflow editor | ProcessStage, ProjectVersion and project workflow API | Editable React Flow stages/edges; desktop/mobile Playwright coverage | PARTIAL: save/reload/conflict path verified; detailed large-graph and keyboard acceptance remains | Validated DAG, editable nodes/edges/details, atomic save, reload, conflict handling, mobile |
| Illustrations | worker provider contract; existing image entity | No functional stage UI | MISSING | Clearly labeled deterministic fallback, private stage association, regenerate/delete |
| Lawyer review | Project review status and role model | No review interface | MISSING | Authorized explicit decisions, comments, reviewer identity/history, edit invalidation |
| Exports | Export entity | No export interface | MISSING | Saved-state PDF/PNG, citations/disclaimer/review status, multi-page layout, access checks |
| Account/settings | Profile update API and settings component | Functional display-name editor and frontend/API tests | PARTIAL: account deletion and broader workspace settings remain | Authorized profile updates and honest available actions |
| Operations | Compose, migrations, readiness, verify scripts | Frontend tests, API focus suite and desktop/mobile Playwright | PARTIAL: full backend suite and production build still pending | Current regression/build/migrations, safe repeatable startup, desktop/mobile |
| Hosted confirmation/storage | Supabase adapters | Controlled transport tests | BLOCKED | Real email/hosted changes prohibited by current request; retain unverified status |
| Production deployment | Existing deployment notes | No deployment requested | DEFERRED | Separate deployment, TLS, restricted runtime DB roles and operational acceptance |

## Fresh evidence

- Focused API/pipeline/workflow regression: 42 passed after correcting the UUID comparison.
- Frontend Vitest: 112 passed; ESLint, TypeScript and Ruff checks passed for the implementation files.
- Full desktop/mobile Playwright suite: 12 passed. After adding explicit per-document cleanup to the E2E flow, the focused desktop/mobile document lifecycle passed 2/2.
- Alembic drift check found no new upgrade operations; readiness and test DB were at `f4a8d1c7e902`.
- The isolated E2E database ended with 10 projects, 1 document and 1 job; the recorded pre-test project/document counts were preserved. No `Process briefing` test projects or local E2E storage files remained.
- Real Ollama model installation/inference and hosted Supabase Auth acceptance remain unverified. External OpenAI processing was disabled.
- An initial misconfigured browser attempt inherited Supabase storage settings and uploaded generated test fixtures. After the user authorized cleanup, five exact remote test-object keys and the four test-created E2E projects were removed. The final accepted browser runs explicitly used local storage and disabled external AI.

## Next execution steps

1. Run the full backend suite, production build and security review against the current tree.
2. Verify a locally installed Ollama model and record the actual inference/embedding result; do not make a paid provider call.
3. Design and implement remaining illustration, lawyer-review and saved-state export work only when authorized.
4. Revisit project-level private-storage cleanup; deleting a project currently leaves files in local storage unless documents are individually deleted first.
