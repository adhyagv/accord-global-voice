from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...privacy import caller_member_id
from ...serializers import serialize_constraint, serialize_constraint_shared
from ...services.use_cases import AccordService

router = APIRouter(prefix="/constraints", tags=["constraints"])


@router.post("/derive/{session_id}")
def derive_constraints(
    session_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    constraints = service.derive_constraints(session_id, requester_member_id)
    return {"constraints": [serialize_constraint(c) for c in constraints]}


@router.get("/members/{member_id}")
def list_member_constraints(
    member_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    constraints = service.list_member_constraints(member_id, requester_member_id)
    return {"constraints": [serialize_constraint(c) for c in constraints]}


@router.get("/households/{household_id}/shared")
def list_shared_constraints(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    constraints = service.list_shareable_constraints(household_id, requester_member_id)
    return {"constraints": [serialize_constraint_shared(c) for c in constraints]}
