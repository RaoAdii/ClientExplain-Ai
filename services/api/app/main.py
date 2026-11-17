import json
import logging
from time import perf_counter
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from starlette.exceptions import HTTPException

from app.api.routes import router
from app.core.config import settings

logging.basicConfig(level=logging.INFO, format="%(message)s")
log = logging.getLogger("clientexplain")
app = FastAPI(
    title="ClientExplain AI API",
    version="0.1.0",
    description="Project foundation. AI-generated explanations require professional review.",
    docs_url="/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
    allow_credentials=False,
)
app.include_router(router)


@app.middleware("http")
async def request_logging(request: Request, call_next):
    request.state.request_id = str(uuid4())
    start = perf_counter()
    response = await call_next(request)
    response.headers["X-Request-ID"] = request.state.request_id
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Cache-Control"] = "no-store"
    log.info(
        json.dumps(
            {
                "event": "request",
                "request_id": request.state.request_id,
                "method": request.method,
                "status": response.status_code,
                "duration_ms": round((perf_counter() - start) * 1000),
            }
        )
    )
    return response


@app.exception_handler(HTTPException)
async def http_error(request, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "message": str(exc.detail),
                "request_id": getattr(request.state, "request_id", None),
            }
        },
        headers=exc.headers,
    )


@app.exception_handler(RequestValidationError)
async def validation_error(request, exc):
    errors = [
        {"field": ".".join(map(str, item["loc"])), "message": item["msg"]} for item in exc.errors()
    ]
    return JSONResponse(
        status_code=422,
        content={"error": {"message": "Check the submitted fields.", "fields": errors}},
    )


@app.exception_handler(SQLAlchemyError)
async def database_error(request, exc):
    log.error(
        json.dumps(
            {
                "event": "database_error",
                "request_id": getattr(request.state, "request_id", None),
                "type": type(exc).__name__,
            }
        )
    )
    return JSONResponse(
        status_code=503,
        content={"error": {"message": "The database is unavailable. Try again shortly."}},
    )


@app.exception_handler(Exception)
async def unexpected_error(request, exc):
    log.error(
        json.dumps(
            {
                "event": "unexpected_error",
                "request_id": getattr(request.state, "request_id", None),
                "type": type(exc).__name__,
            }
        )
    )
    return JSONResponse(
        status_code=500,
        content={"error": {"message": "An unexpected error occurred. Please try again."}},
    )
