"""FastAPI application factory."""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from fittrack.api.middleware import setup_middleware
from fittrack.core.config import Settings
from fittrack.core.database import close_pool, init_pool
from fittrack.core.logging import setup_logging

logger = logging.getLogger(__name__)


def create_app(settings: Settings | None = None) -> FastAPI:
    """Create and configure the FastAPI application."""
    if settings is None:
        settings = Settings()

    # Configure structured logging
    if not settings.is_testing:
        setup_logging(level=settings.log_level, log_format=settings.log_format)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        logger.info("Starting FitTrack API (env=%s)", settings.app_env)
        if not settings.is_testing:
            try:
                pool = await init_pool(settings)
                app.state.db_pool = pool
                logger.info("Database pool ready")
            except Exception:
                logger.warning(
                    "Could not connect to Oracle — API will start without DB. "
                    "Use /api/v1/dev/migrate once Oracle is ready."
                )
                app.state.db_pool = None
        yield
        logger.info("Shutting down FitTrack API")
        if not settings.is_testing:
            await close_pool()

    application = FastAPI(
        title="FitTrack API",
        description="Gamified fitness platform API",
        version="0.1.0",
        docs_url="/docs",
        redoc_url="/redoc",
        lifespan=lifespan,
    )

    # Store settings on app state
    application.state.settings = settings

    # Middleware
    setup_middleware(application)

    # Profile gate middleware (must be after CORS/logging, before routes)
    from fittrack.api.profile_gate import profile_gate_middleware

    @application.middleware("http")
    async def _profile_gate(request: Request, call_next):  # type: ignore[no-untyped-def]
        return await profile_gate_middleware(request, call_next)

    # Register routers
    _register_routes(application)

    # Mount static files (test page)
    static_dir = Path(__file__).resolve().parent.parent.parent / "static"
    if static_dir.is_dir():
        application.mount(
            "/static", StaticFiles(directory=str(static_dir), html=True), name="static"
        )

    return application


def _register_routes(app: FastAPI) -> None:
    """Register all API route modules."""
    from fittrack.api.routes.activities import router as activities_router
    from fittrack.api.routes.admin_analytics import router as admin_analytics_router
    from fittrack.api.routes.admin_users import router as admin_users_router
    from fittrack.api.routes.auth import router as auth_router
    from fittrack.api.routes.connections import router as connections_router
    from fittrack.api.routes.dev import router as dev_router
    from fittrack.api.routes.drawings import router as drawings_router
    from fittrack.api.routes.fulfillments import router as fulfillments_router
    from fittrack.api.routes.health import router as health_router
    from fittrack.api.routes.leaderboards import router as leaderboards_router
    from fittrack.api.routes.me import public_router as public_profile_router
    from fittrack.api.routes.me import router as me_router
    from fittrack.api.routes.notifications import router as notifications_router
    from fittrack.api.routes.points import router as points_router
    from fittrack.api.routes.prizes import router as prizes_router
    from fittrack.api.routes.profiles import router as profiles_router
    from fittrack.api.routes.sponsors import router as sponsors_router
    from fittrack.api.routes.tickets import router as tickets_router
    from fittrack.api.routes.tiers import router as tiers_router
    from fittrack.api.routes.transactions import router as transactions_router
    from fittrack.api.routes.users import router as users_router

    app.include_router(health_router, tags=["health"])
    app.include_router(auth_router)
    app.include_router(me_router)
    app.include_router(users_router)
    app.include_router(public_profile_router)
    app.include_router(profiles_router)
    app.include_router(tiers_router)
    app.include_router(connections_router)
    app.include_router(activities_router)
    app.include_router(transactions_router)
    app.include_router(points_router)
    app.include_router(leaderboards_router)
    app.include_router(drawings_router)
    app.include_router(tickets_router)
    app.include_router(prizes_router)
    app.include_router(fulfillments_router)
    app.include_router(sponsors_router)
    app.include_router(admin_users_router)
    app.include_router(admin_analytics_router)
    app.include_router(notifications_router)
    app.include_router(dev_router)


# Module-level app instance for uvicorn (uvicorn fittrack.main:app)
app = create_app()
