from app.api import auth, documents, projects
from app.db.session import SessionLocal, redis_client
from fastapi import APIRouter, HTTPException
from sqlalchemy import text

router = APIRouter(prefix="/api/v1")
router.include_router(auth.router)
router.include_router(projects.router)
router.include_router(documents.router)


@router.get("/health", tags=["Operations"])
def health():
    return {"status": "ok", "service": "clientexplain-api", "version": "0.1.0"}


@router.get("/health/ready", tags=["Operations"])
def ready():
    try:
        with SessionLocal() as db:
            revision = db.scalar(text("SELECT version_num FROM alembic_version"))
            if revision != "d14c3a7f2901":
                raise RuntimeError("Database migrations are not current")
            db.execute(text("SELECT 1 FROM projects LIMIT 0"))
        redis_client.ping()
    except Exception as exc:
        raise HTTPException(503, "Database or queue is unavailable") from exc
    return {"status": "ready", "database": "connected", "redis": "connected"}
