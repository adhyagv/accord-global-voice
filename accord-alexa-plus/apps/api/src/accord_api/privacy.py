"""Privacy and authorization guards."""

from __future__ import annotations

from fastapi import Header

from .errors import ApiError


RESOURCE_NOT_FOUND = ApiError(
    code="resource_not_found",
    message="Requested resource was not found.",
    status_code=404,
)


def caller_member_id(x_member_id: str | None = Header(default=None)) -> str:
    if not x_member_id:
        raise ApiError("missing_member_context", "X-Member-Id header is required.", 401)
    return x_member_id


def require_same_member(requester_member_id: str, owner_member_id: str) -> None:
    if requester_member_id != owner_member_id:
        # Hide resource existence for unauthorized callers.
        raise RESOURCE_NOT_FOUND


def require_household_membership(requester_member_id: str, household_member_ids: set[str]) -> None:
    if requester_member_id not in household_member_ids:
        raise RESOURCE_NOT_FOUND
