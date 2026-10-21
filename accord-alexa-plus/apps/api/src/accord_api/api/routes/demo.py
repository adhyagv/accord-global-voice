from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...serializers import (
    serialize_agreement,
    serialize_assignment,
    serialize_household,
    serialize_member,
    serialize_signal,
)
from ...services.use_cases import AccordService

router = APIRouter(prefix="/demo", tags=["demo"])


@router.post("/roommates/reset", status_code=201)
def reset_demo_roommates(service: AccordService = Depends(get_service)) -> dict:
    """DEVELOPMENT/DEMO ONLY: reset deterministic three-roommate scenario."""
    demo = service.demo_roommates_reset()
    return {
        "mode": demo["mode"],
        "household": serialize_household(demo["household"]),
        "members": [serialize_member(m) for m in demo["members"]],
        "agreement": serialize_agreement(demo["agreement"]),
        "assignments": [serialize_assignment(a) for a in demo["assignments"]],
        "monitoringSignals": [serialize_signal(s) for s in demo["monitoringSignals"]],
        "simulatedIntegrations": demo["simulatedIntegrations"],
    }
