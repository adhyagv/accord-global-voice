from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...privacy import caller_member_id
from ...serializers import serialize_signal
from ...services.use_cases import AccordService
from ..schemas import RecordMonitoringSignalRequest

router = APIRouter(prefix="/monitoring", tags=["monitoring"])


@router.get("/weekly-digest/{household_id}")
def weekly_digest(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Generate an on-demand seven-day digest from recorded prototype data."""
    return service.weekly_digest(household_id, requester_member_id)


@router.post("/signals", status_code=201)
def record_signal(
    payload: RecordMonitoringSignalRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    signal = service.record_monitoring_signal(
        household_id=payload.householdId,
        requester_member_id=requester_member_id,
        assignment_reference=payload.assignmentReference,
        member_reference=payload.memberReference,
        expected_contribution=payload.expectedContribution,
        observed_contribution=payload.observedContribution,
        timestamp=payload.timestamp,
    )
    return {"signal": serialize_signal(signal)}


@router.get("/signals/households/{household_id}")
def list_signals(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    signals = service.list_monitoring_signals(household_id, requester_member_id)
    return {"signals": [serialize_signal(s) for s in signals]}


@router.get("/workload-drift/{household_id}")
def workload_drift(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Calculate a non-notifying, three-week completed-work imbalance alert."""
    return service.workload_drift_alert(household_id, requester_member_id)
