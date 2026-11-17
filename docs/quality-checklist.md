# Global quality checklist

Updated 2026-11-17. This checklist covers implemented Step 1 surfaces and must be repeated after each later stage. Passing the foundation does not certify legal compliance or production readiness of unfinished capabilities.

| # | Requirement | Step 1 status / evidence |
|---|---|---|
| 1 | No horizontal scrolling | Browser checks at desktop, mobile and 320px widths |
| 2 | Fix broken links | Browser checks of public internal links and project navigation |
| 3 | Functional mobile navigation | Public and workspace menus exercised in Playwright |
| 4 | Favicon | Local SVG icon responds successfully |
| 5 | Correct page titles | Unique metadata per page, product name included |
| 6 | Meaningful descriptions | Public and app metadata implemented |
| 7 | Footer links | Privacy and terms routes implemented and checked |
| 8 | Custom 404 | Real 404 response and recovery link verified |
| 9 | Dynamic copyright year | Rendered with current year in both footers |
| 10 | Optimized images | No raster assets; compact SVG favicon and Lucide icons |
| 11 | No broken buttons | Project CRUD, cancellation, retry, local login, sign-out tested; future actions are not offered |
| 12 | Success messages | Real successful mutations trigger accessible notifications |
| 13 | Useful errors | Validation, API failures, session failures and missing projects have explicit states |
| 14 | No unfinished placeholder copy | Product-specific text and honest empty states; legal draft gaps are explicitly explained |
| 15 | No unused navigation | Only implemented pages are linked |
| 16 | Fix mobile overflow | Automated viewport assertions and screenshots |
| 17 | Clickable logo | Landing-page link in public, footer and app navigation |
| 18 | Clickable real phone numbers | Not applicable: no phone numbers invented or displayed |
| 19 | Clickable real email addresses | Configured account email uses mailto; no invented business email |
| 20 | Mobile pages | Public, workspace, project detail and settings checked in Chromium mobile emulation |
| 21 | Custom domain preparation | NEXT_PUBLIC_SITE_URL controls canonical origin; actual domain remains an operator choice |
| 22 | Meaningful URLs | /login, /register, /dashboard/projects, /dashboard/settings, /privacy, /terms |
| 23 | Unique metadata and canonicals | Metadata helper, dynamic project canonical, private-page noindex |
| 24 | One primary H1 | Public pages asserted; app pages each have one PageHeader |
| 25 | Discovery files | sitemap.xml, robots.txt and llms.txt verified |
| 26 | No purple gradients | Teal, neutral and warm off-white CSS palette; no gradients |
| 27 | No pills, fabricated reviews or metrics | Squared rounded controls; empty workspace; no synthetic activity |
| 28 | No vague hero, emojis, em dashes, excessive animation | Product-specific headline, Lucide icons; reduced-motion CSS |
| 29 | No Made with AI label | No such label in application copy |
| 30 | Privacy and terms | Separate substantive draft pages requiring actual business/jurisdiction review |
| 31 | No generic AI photos, cursor effects or customer counters | No photographic imagery, cursor effects or counters |
| 32 | Verify changes | Pytest, Vitest, Playwright, axe, Ruff, ESLint, TypeScript, Next production build and schema drift checks |

## Additional checks

- Semantic landmarks, associated labels, visible keyboard focus and skip link.
- Automated WCAG A/AA checks on public pages and dashboard; this does not replace a full assistive-technology audit.
- Zod and Pydantic validate inputs independently; whitespace-only names, oversized input, explicit null updates and unknown fields are rejected.
- Loading, empty, success and error states; no raw database exceptions exposed.
- Browser tests fail on uncaught JavaScript errors in normal navigation/CRUD flows.
- Real relational persistence, foreign keys, composite tenant references, audit records and database update timestamps.
- JWT issuer/audience/expiry/signature validation configured for Supabase asymmetric JWKS; live Supabase verification is pending actual project configuration.
- Server-side development token remains outside the browser bundle; local HTTP-only cookie and same-origin mutation checks.
- RLS independently tested under a non-superuser role; local bootstrap superuser remains unsuitable as a production runtime account.
- Credentials are generated into ignored local env files; package and Python dependency versions are locked.
- No AI inference or fabricated legal output in the API process.

## Required before later production delivery

- Configure and test real Supabase registration, confirmation, sign-in, recovery, key rotation and account removal.
- Implement and verify private Storage policies with document processing.
- Benchmark and license-check a diffusion model; implement local/hosted adapters and resource limits. No model or embedding dimension selected yet.
- Implement retrieval/citation quality controls, mandatory professional review, versioning and exports in their designated stages.
- Apply production runtime DB role, TLS, rate limiting, backup/restore testing, retention and incident response.
- Obtain actual business identity, verified contact details and jurisdiction-specific legal review of the draft policies.
- Run CI in GitHub after the owner creates/connects a remote; this session performs local checks only.
- Test Firefox, Safari and real mobile devices before public launch; current automated browser coverage is Chromium desktop and mobile emulation.
