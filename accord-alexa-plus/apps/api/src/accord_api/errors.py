"""Shared API errors and exception handlers."""

from __future__ import annotations

from dataclasses import dataclass
from uuid import uuid4

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ApiError(Exception):
    code: str
    message: str
    status_code: int


def _request_id_from(request: Request) -> str:
    return request.headers.get("x-request-id") or str(uuid4())


def error_response(request: Request, code: str, message: str, status_code: int) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {"code": code, "message": message, "request_id": _request_id_from(request)}
        },
    )


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error_response(request, exc.code, exc.message, exc.status_code)


async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return error_response(request, "validation_error", "Request validation failed.", 422)


async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    return error_response(request, "internal_error", "Internal server error.", 500)
