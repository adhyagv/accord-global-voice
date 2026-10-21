from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...privacy import caller_member_id
from ...serializers import serialize_interview_private, serialize_interview_shared
from ...services.use_cases import AccordService
from ..schemas import StartInterviewRequest, SubmitInterviewRequest

router = APIRouter(prefix="/interviews", tags=["interviews"])


@router.post("", status_code=201)
def start_interview(payload: StartInterviewRequest, service: AccordService = Depends(get_service)) -> dict:
    session = service.start_interview(payload.householdId, payload.memberId)
    return {"session": serialize_interview_shared(session)}


@router.post("/{session_id}/submit")
def submit_interview(
    session_id: str,
    payload: SubmitInterviewRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    session = service.submit_interview(
        session_id,
        requester_member_id,
        payload.transcriptReference,
        payload.answers,
    )
    return {"session": serialize_interview_shared(session)}


@router.post("/{session_id}/complete")
def complete_interview(
    session_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    session = service.complete_interview(session_id, requester_member_id)
    return {"session": serialize_interview_shared(session)}


@router.get("/{session_id}/private")
def get_private_interview(
    session_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    session = service.get_private_interview(session_id, requester_member_id)
    return {"session": serialize_interview_private(session)}
