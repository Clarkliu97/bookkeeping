import logging
import time
from uuid import uuid4

from fastapi import Depends, FastAPI, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.api.deps import get_db
from app.api.router import api_router
from app.core.config import get_settings
from app.core.logging import configure_logging, request_id_context
from app.core.observability import observability_store


settings = get_settings()
configure_logging(settings)
logger = logging.getLogger("bookkeeping_tax.api")

app = FastAPI(
    title="Bookkeeping Tax API",
    version="0.1.0",
    description=(
        "Internal bookkeeping and tax support API for Australian companies. "
        "This system prepares reviewable reports and workpapers only."
    ),
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
    allow_origin_regex=settings.allowed_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix=settings.api_prefix)


@app.middleware("http")
async def add_request_context(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or str(uuid4())
    token = request_id_context.set(request_id)
    start = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
    except Exception:
        duration_ms = round((time.perf_counter() - start) * 1000, 2)
        observability_store.record_request(request.method, request.url.path, status_code, duration_ms)
        logger.exception(
            "request.failed",
            extra={
                "method": request.method,
                "path": request.url.path,
                "status_code": status_code,
                "duration_ms": duration_ms,
            },
        )
        request_id_context.reset(token)
        raise
    duration_ms = round((time.perf_counter() - start) * 1000, 2)
    observability_store.record_request(request.method, request.url.path, status_code, duration_ms)
    response.headers["X-Request-ID"] = request_id
    logger.info(
        "request.completed",
        extra={
            "method": request.method,
            "path": request.url.path,
            "status_code": response.status_code,
            "duration_ms": duration_ms,
        },
    )
    request_id_context.reset(token)
    return response


def _readiness_status(db: Session) -> tuple[dict[str, object], int]:
    checks: dict[str, str] = {"database": "unknown", "documents": "unknown"}
    try:
        db.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "error"

    try:
        from app.documents.service import document_storage_root

        document_storage_root()
        checks["documents"] = "ok"
    except Exception:
        checks["documents"] = "error"

    overall_status = "ok" if all(value == "ok" for value in checks.values()) else "degraded"
    observability_store.record_readiness(overall_status, checks)
    if overall_status != "ok":
        observability_store.emit_alert(
            code="readiness_degraded",
            severity="warning",
            message="Application readiness degraded",
            details={"checks": checks, "environment": settings.environment},
            settings=settings,
            logger=logger,
        )
    http_status = 200 if overall_status == "ok" else 503
    return {
        "status": overall_status,
        "environment": settings.environment,
        "checks": checks,
    }, http_status


@app.get("/health", tags=["system"])
def healthcheck(db: Session = Depends(get_db)) -> JSONResponse:
    payload, status_code = _readiness_status(db)
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/health/live", tags=["system"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["system"])
def readiness(db: Session = Depends(get_db)) -> JSONResponse:
    payload, status_code = _readiness_status(db)
    return JSONResponse(status_code=status_code, content=payload)


@app.get("/metrics", tags=["system"])
def metrics() -> PlainTextResponse:
    if not settings.metrics_enabled:
        return PlainTextResponse(status_code=404, content="metrics disabled\n")
    return PlainTextResponse(content=observability_store.render_metrics(), media_type="text/plain; version=0.0.4")


@app.get("/alerts/recent", tags=["system"])
def recent_alerts() -> dict[str, object]:
    alerts = observability_store.recent_alerts()
    return {"items": alerts, "count": len(alerts)}
