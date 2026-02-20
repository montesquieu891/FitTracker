"""Health check routes — liveness, readiness, and general health."""

from __future__ import annotations

import time
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter()


@router.get("/health")
def health_check(request: Request) -> dict[str, Any]:
    """Application health check endpoint."""
    settings = getattr(request.app.state, "settings", None)
    env = settings.app_env if settings else "unknown"

    db_pool = getattr(request.app.state, "db_pool", None)
    db_status = "connected" if db_pool is not None else "disconnected"

    return {
        "status": "ok",
        "environment": env,
        "database": db_status,
    }


@router.get("/health/live")
def liveness_probe() -> dict[str, Any]:
    """Liveness probe — is the process alive and responding?

    Returns 200 if the application can handle requests.
    Kubernetes uses this to decide whether to restart the container.
    """
    return {"status": "alive"}


@router.get("/health/ready")
def readiness_probe(request: Request) -> dict[str, Any]:
    """Readiness probe — is the application ready to serve traffic?

    Checks database connectivity and critical dependencies.
    Kubernetes uses this to decide whether to route traffic.
    """
    checks: dict[str, Any] = {}
    overall_ready = True

    # Database check
    db_pool = getattr(request.app.state, "db_pool", None)
    if db_pool is not None:
        try:
            start = time.perf_counter()
            conn = db_pool.acquire()
            try:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM DUAL")
                    cur.fetchone()
                elapsed_ms = (time.perf_counter() - start) * 1000
                checks["database"] = {
                    "status": "ok",
                    "response_time_ms": round(elapsed_ms, 1),
                }
            finally:
                conn.close()
        except Exception as exc:
            checks["database"] = {"status": "error", "detail": str(exc)}
            overall_ready = False
    else:
        checks["database"] = {"status": "not_configured"}
        # In testing/dev, missing DB doesn't make us unready
        settings = getattr(request.app.state, "settings", None)
        if settings and settings.is_production:
            overall_ready = False

    body = {
        "status": "ready" if overall_ready else "not_ready",
        "checks": checks,
    }
    if not overall_ready:
        return JSONResponse(content=body, status_code=503)
    return body
