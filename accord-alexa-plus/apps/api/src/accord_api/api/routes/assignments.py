from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...models import AssignmentStatus
from ...privacy import caller_member_id
from ...serializers import serialize_assignment
from ...services.use_cases import AccordService
from ..schemas import CreateAssignmentRequest, ReassignAssignmentRequest, UpdateAssignmentStatusRequest

router = APIRouter(prefix="/assignments", tags=["assignments"])


@router.post("", status_code=201)
def create_assignment(
    payload: CreateAssignmentRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    assignment = service.create_assignment(
        household_id=payload.householdId,
        requester_member_id=requester_member_id,
        member_id=payload.memberId,
        task=payload.task,
        frequency=payload.frequency,
        estimated_effort=payload.estimatedEffort,
        assigned_date=payload.assignedDate,
    )
    return {"assignment": serialize_assignment(assignment)}


@router.get("/households/{household_id}")
def list_assignments(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    assignments = service.list_assignments(household_id, requester_member_id)
    return {"assignments": [serialize_assignment(a) for a in assignments]}


@router.patch("/{assignment_id}/status")
def update_assignment_status(
    assignment_id: str,
    payload: UpdateAssignmentStatusRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    assignment = service.update_assignment_status(
        assignment_id, requester_member_id, AssignmentStatus(payload.status)
    )
    return {"assignment": serialize_assignment(assignment)}


@router.post("/{assignment_id}/reassign")
def reassign_assignment(
    assignment_id: str,
    payload: ReassignAssignmentRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Apply a confirmed reassign action; the current demo member must belong to the household."""
    assignment = service.reassign_assignment(assignment_id, requester_member_id, payload.memberId)
    return {"assignment": serialize_assignment(assignment), "confirmationRecorded": True}
