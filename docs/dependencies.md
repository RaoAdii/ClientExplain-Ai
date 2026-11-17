# Installed dependency versions

Resolved from package-lock.json and the Python 3.11 environment.

## Frontend and tooling

| Package | Version |
|---|---|
| @axe-core/playwright | 4.14.0 |
| @hookform/resolvers | 7.0.7 |
| @playwright/test | 1.65.1 |
| @radix-ui/react-slot | 1.5.0 |
| @supabase/supabase-js | 2.119.0 |
| @tailwindcss/postcss | 4.3.5 |
| @tanstack/react-query | 5.107.2 |
| @types/node | 26.6.6 |
| @types/react | 19.3.0 |
| @types/react-dom | 19.3.0 |
| @xyflow/react | 13.0.1 |
| class-variance-authority | 0.7.1 |
| clsx | 2.1.1 |
| eslint | 9.39.5 |
| eslint-config-next | 16.4.6 |
| lucide-react | 1.74.0 |
| next | 16.4.6 |
| node | 22.23.5 |
| prettier | 3.10.1 |
| react | 19.3.1 |
| react-dom | 19.3.1 |
| react-hook-form | 7.92.0 |
| tailwind-merge | 3.7.0 |
| tailwindcss | 4.3.5 |
| typescript | 6.0.3 |
| vitest | 5.1.0 |
| zod | 4.6.7 |
| zustand | 5.1.0 |

shadcn/ui uses source components, not a runtime package. Button follows its Radix Slot/CVA pattern.

## Python

| Package | Version |
|---|---|
| fastapi | 0.163.1 |
| uvicorn | 0.54.0 |
| pydantic | 2.14.3 |
| pydantic-settings | 2.16.3 |
| SQLAlchemy | 2.0.58 |
| alembic | 1.20.1 |
| psycopg | 3.3.9 |
| pgvector | 0.5.1 |
| redis | 6.4.0 |
| celery | 5.7.0 |
| PyJWT | 2.15.1 |
| pytest | 9.2.0 |
| ruff | 0.17.5 |
| httpx | 0.28.1 |
| httpx2 | 2.16.2 |

Full transitive pins: services/api/requirements.lock. AI inference libraries are deferred until model/provider selection; none load into FastAPI.
