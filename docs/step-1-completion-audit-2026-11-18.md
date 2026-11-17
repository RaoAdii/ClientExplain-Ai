# Step 1 completion audit

Audited 18 November 2026. **Overall status: COMPLETE for all locally verifiable Step 1 requirements.** Step 2 was not started. Live Supabase, a production domain, remote GitHub Actions, jurisdiction-specific legal approval and physical cross-browser/device testing remain external requirements.

## Audit changes

- Made server and public auth modes explicit and fail-fast when mismatched.
- Separated login validation from the stronger registration password rule.
- Added actionable recovery controls to project-detail failures.
- Increased the BFF body limit so the valid 10,000-character description survives JSON escaping.
- Removed redundant legacy httpx/httpcore; retained the Starlette-compatible httpx2 implementation.
- Added `scripts/audit_migrations.py` for disposable upgrade, downgrade and re-upgrade verification.
- Expanded Playwright coverage for 375, 768, 1024 and 1440 pixel widths, maximum payloads, console errors and detail retry behavior.
- Added API CORS preflight/readiness coverage and refreshed setup/deployment documentation.

## Verification results

| Area | Result |
|---|---|
| ESLint / TypeScript / Next production build | PASS; 13 pages generated |
| Vitest / Playwright | PASS; 4 / 10 tests |
| Responsive layout | PASS; 320, 375, 768, 1024 and 1440 px |
| Accessibility | PASS; no axe WCAG A/AA findings on tested surfaces |
| Ruff lint / format / Pytest | PASS; 24 files / 12 tests |
| pip check / npm production audit | PASS; no broken requirements / 0 reported vulnerabilities |
| Alembic | PASS; head `c62fbd003112`, no model drift |
| Disposable migration round trip | PASS; upgrade, downgrade and re-upgrade |
| Docker build and runtime | PASS; API/worker rebuilt; four services healthy |
| PostgreSQL / pgvector | PASS; vector 0.8.7; 16 public tables |
| Schema integrity | PASS; zero invalid indexes and unvalidated constraints |
| Redis / Celery | PASS; PONG, worker ping and completed queued health task |
| Persistence | PASS; project survived PostgreSQL restart, then was removed |
| Live readiness | PASS; database and Redis connected |
| Secret scan | PASS; no tracked local env files or recognized credential patterns |

The expected network 404 produced while validating the custom not-found route is excluded from the unexpected-console-error assertion. Normal navigation and CRUD flows had no uncaught browser errors.

## Issues found and fixed

1. Public and server auth modes could diverge. Configuration now documents both and the build rejects mismatches.
2. Login incorrectly inherited registration password length. Login now accepts an existing non-empty password; registration still requires eight characters.
3. Project-detail failures lacked recovery actions. Retry and return controls were added.
4. The BFF cap could reject a valid escaped maximum-length description. Its safe request limit was raised.
5. Legacy httpx duplicated the compatible httpx2 fork. The unused packages were removed and locks refreshed.
6. Migration downgrade/re-upgrade was manual. A disposable database audit now automates it.
7. The first Docker rebuild met slow registry downloads; a cached retry completed without suppressing errors.

## External blockers

- **BLOCKED:** Live Supabase signup, confirmation, recovery, deletion and private Storage checks require project credentials.
- **BLOCKED:** Domain, DNS, TLS and production canonical URL require a deployment/domain decision.
- **BLOCKED:** Remote GitHub Actions requires a connected remote and push.
- **BLOCKED:** Final Privacy/Terms approval requires business identity, jurisdictions and legal counsel.
- **BLOCKED:** Safari, Firefox and physical-device verification require those environments; local Chromium emulation passed.

These are production inputs, not local Step 1 setup failures.

## Original 32-point checklist

| # | Status | Evidence |
|---|---|---|
| 1 | PASS | No overflow at all tested widths. |
| 2 | PASS | Public and application links were exercised. |
| 3 | PASS | Both mobile menus work. |
| 4 | PASS | Reachable SVG favicon. |
| 5 | PASS | Correct unique route titles. |
| 6 | PASS | Meaningful route descriptions. |
| 7 | PASS | Privacy and Terms footer links work. |
| 8 | PASS | Real 404 response and custom recovery UI. |
| 9 | PASS | Render-time copyright year. |
| 10 | PASS | No raster content; optimized SVG/Lucide assets. |
| 11 | PASS | Implemented buttons and CRUD actions tested. |
| 12 | PASS | Mutation success notifications tested. |
| 13 | PASS | Actionable validation, service, session and not-found errors. |
| 14 | PASS | No unfinished placeholder copy; legal review markers are intentional. |
| 15 | PASS | Navigation contains implemented routes only. |
| 16 | PASS | Mobile overflow assertions pass. |
| 17 | PASS | Public and workspace logos link home. |
| 18 | PASS | No phone is displayed, so none is non-clickable. |
| 19 | PASS | Account email uses mailto; no business email invented. |
| 20 | PASS | Every implemented page checked in mobile emulation. |
| 21 | PASS | Origin is configurable; actual domain is externally blocked. |
| 22 | PASS | Clean, meaningful slugs. |
| 23 | PASS | Titles, descriptions and canonical tags verified. |
| 24 | PASS | One primary H1 on tested pages. |
| 25 | PASS | sitemap.xml, robots.txt and llms.txt verified. |
| 26 | PASS | No purple gradients. |
| 27 | PASS | No pills, fake reviews or metrics. |
| 28 | PASS | Specific copy; no emoji, em dashes or excessive animation. |
| 29 | PASS | No “Made with AI” label. |
| 30 | PASS | Privacy and Terms drafts exist and require legal review. |
| 31 | PASS | No AI-stock photos, cursor effects or customer counters. |
| 32 | PASS | Tests, builds, migrations and live probes passed. |

## Commands

Start from PowerShell:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/setup.ps1
docker compose --profile app up -d --wait
npm run dev
```

Open `http://localhost:3000`; API docs are at `http://localhost:8000/docs`.

Repeat the audit:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/verify.ps1
.\.venv\Scripts\python.exe scripts/audit_migrations.py
npm run test:e2e
npm run build
docker compose --profile app ps
```

Stop without deleting persistent volumes:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File scripts/stop-web.ps1
docker compose --profile app down
```
