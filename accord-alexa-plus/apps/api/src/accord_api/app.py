"""FastAPI application entrypoint for Accord backend core service."""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware

from .api.routes import (
    agreements_router,
    alexa_router,
    clauses_router,
    fairness_router,
    mediation_router,
    assistant_router,
    assignments_router,
    constraints_router,
    demo_router,
    drift_router,
    expenses_router,
    households_router,
    interviews_router,
    monitoring_router,
    privacy_dashboard_router,
)
from .config import settings
from .dependencies import get_context
from .errors import (
    ApiError,
    api_error_handler,
    unhandled_error_handler,
    validation_error_handler,
)


logger = logging.getLogger("accord.persistence")


def create_app() -> FastAPI:
    app = FastAPI(
        title=settings.api_title,
        version=settings.api_version,
        description="Accord backend core service (simulated integrations only).",
    )

    # Allow the local React development server to call this API.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
        allow_origin_regex=r"^https?://(localhost|127\.0\.0\.1)(:\d+)?$",
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(
        RequestValidationError, validation_error_handler
    )
    app.add_exception_handler(Exception, unhandled_error_handler)

    @app.middleware("http")
    async def persist_after_request(request, call_next):
        response = await call_next(request)
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            try:
                # Snapshot writes are local SQLite transactions. Keep the API response
                # available even if a disk write fails, but record the failure clearly.
                context = get_context()
                context.persist()
            except Exception:
                logger.exception("Failed to persist Accord state to SQLite")
        return response

    app.include_router(assistant_router, prefix=settings.api_prefix)
    app.include_router(households_router, prefix=settings.api_prefix)
    app.include_router(interviews_router, prefix=settings.api_prefix)
    app.include_router(constraints_router, prefix=settings.api_prefix)
    app.include_router(agreements_router, prefix=settings.api_prefix)
    app.include_router(clauses_router, prefix=settings.api_prefix)
    app.include_router(fairness_router, prefix=settings.api_prefix)
    app.include_router(mediation_router, prefix=settings.api_prefix)
    app.include_router(alexa_router, prefix=settings.api_prefix)
    app.include_router(assignments_router, prefix=settings.api_prefix)
    app.include_router(monitoring_router, prefix=settings.api_prefix)
    app.include_router(privacy_dashboard_router, prefix=settings.api_prefix)
    app.include_router(drift_router, prefix=settings.api_prefix)
    app.include_router(expenses_router, prefix=settings.api_prefix)
    app.include_router(demo_router, prefix=settings.api_prefix)

    @app.get("/healthz", tags=["system"])
    def healthz() -> dict:
        context = get_context()
        return {
            "status": "ok",
            "mode": "simulated",
            "storage": "sqlite" if context.snapshot_store is not None else "memory",
        }

    return app


app = create_app()