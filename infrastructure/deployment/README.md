# Deployment boundary

This is a verified local foundation, not a production launch authorization.
Set APP_ENV=production and AUTH_MODE=supabase; development authentication is rejected by FastAPI.
Remove DEV_AUTH_TOKEN and development seed data. Set explicit HTTPS CORS_ORIGINS, Supabase URL/JWKS, and web NEXT_PUBLIC_SUPABASE_URL/NEXT_PUBLIC_SUPABASE_PUBLISHABLE_KEY.
Set NEXT_PUBLIC_SITE_URL to the actual custom-domain origin before building. No domain is invented.
Use a reverse proxy with TLS and rate limits; keep PostgreSQL, Redis and the API off public interfaces.
Use a restricted runtime database role and separate migrations role. RLS context is set transactionally by the API.
Store secrets in the deployment secret manager, never NEXT_PUBLIC variables except the intentionally public Supabase publishable key.
Validate email confirmation, recovery, JWT key rotation, private storage policies, backups, retention, incident response, dependency updates and the legal drafts before handling client data.
Supabase Storage upload/download is deliberately deferred until document processing; no public bucket is created.
