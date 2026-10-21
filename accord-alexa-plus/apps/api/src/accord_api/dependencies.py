"""Dependency wiring for FastAPI routes."""

from __future__ import annotations

from .services.context import AppContext, build_context
from .services.use_cases import AccordService

_CTX: AppContext | None = None
_SERVICE: AccordService | None = None


def get_context() -> AppContext:
    global _CTX
    if _CTX is None:
        _CTX = build_context()
    return _CTX


def get_service() -> AccordService:
    global _SERVICE
    if _SERVICE is None:
        _SERVICE = AccordService(get_context())
    return _SERVICE
