# Operational checks

- GET /api/v1/health: API process liveness.
- GET /api/v1/health/ready: database and Redis connectivity; 503 on failure.
- Docker Compose health checks cover PostgreSQL, Redis and the API.
- Celery: docker compose --profile app exec worker celery -A worker.celery_app:app inspect ping.
- API logs contain JSON request IDs, duration, method and status. They omit tokens, request bodies, legal content and raw database exceptions.
- Production follow-up: persistent log sink, alerts, rate limiting, readiness access controls, backup monitoring and a restoration drill.
