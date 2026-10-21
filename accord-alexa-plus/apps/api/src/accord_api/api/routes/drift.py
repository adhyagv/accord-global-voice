from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...privacy import caller_member_id
from ...serializers import serialize_drift, serialize_interview_shared, serialize_renegotiation
from ...services.use_cases import AccordService
from ..schemas import GenerateDriftReportRequest, StartRenegotiationRequest

router = APIRouter(prefix="/drift", tags=["drift"])


@router.post("/generate", status_code=201)
def generate_drift(
    payload: GenerateDriftReportRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    report = service.generate_drift_report(payload.agreementId, payload.version, requester_member_id)
    return {"driftReport": serialize_drift(report)}


@router.get("/{drift_id}")
def get_drift(
    drift_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    report = service.get_drift_report(drift_id, requester_member_id)
    return {"driftReport": serialize_drift(report)}


@router.post("/renegotiations/start", status_code=201)
def start_renegotiation(
    payload: StartRenegotiationRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    cycle, sessions = service.start_renegotiation(
        payload.householdId, payload.driftId, requester_member_id
    )
    return {
        "renegotiation": serialize_renegotiation(cycle),
        "interviewSessions": [serialize_interview_shared(s) for s in sessions],
    }
