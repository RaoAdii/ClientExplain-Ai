# Tenant isolation

Canonical policies live in Alembic revision c62fbd003112, not a parallel SQL migration history.
Every tenant table has forced row-level security using transaction-local app.firm_id.
Profiles use app.user_id, and membership discovery is limited to that verified subject.
The API authenticates first, resolves membership server-side and sets both context values per transaction.
Never expose a database connection to clients or let callers set tenant context.

Local Compose uses a bootstrap superuser so migrations and tests can prepare fixtures. PostgreSQL superusers bypass RLS; API tenant predicates still apply. Production requires a separate non-owner, non-superuser, NOBYPASSRLS runtime role with SELECT/INSERT/UPDATE/DELETE on application tables, excluding DDL and CREATE privileges. Keep migration credentials separate. Tests exercise policies under a temporary restricted role.

Supabase deployments: use direct/session database connections for migration, deny anon/authenticated access to these application tables through the Data API, and use FastAPI as the only data gateway. No auth.users or auth.uid() references are used. Do not deploy until the actual project's grants and storage policies have been reviewed.
