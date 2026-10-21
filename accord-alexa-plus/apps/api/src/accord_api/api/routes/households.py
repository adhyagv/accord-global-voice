from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...models import ConsentStatus, PrivacyStatus
from ...privacy import caller_member_id
from ...serializers import serialize_household, serialize_member
from ...services.use_cases import AccordService
from ..schemas import AddMemberRequest, CreateHouseholdRequest, UpdateMemberConsentRequest

router = APIRouter(prefix="/households", tags=["households"])


@router.post("", status_code=201)
def create_household(payload: CreateHouseholdRequest, service: AccordService = Depends(get_service)) -> dict:
    household = service.create_household(payload.name, payload.scenarioMetadata)
    return {"household": serialize_household(household)}


@router.get("/{household_id}")
def get_household(household_id: str, service: AccordService = Depends(get_service)) -> dict:
    household = service.get_household(household_id)
    return {"household": serialize_household(household)}


@router.post("/{household_id}/members", status_code=201)
def add_member(
    household_id: str, payload: AddMemberRequest, service: AccordService = Depends(get_service)
) -> dict:
    member = service.add_member(
        household_id=household_id,
        display_name=payload.displayName,
        role=payload.role,
        # Inviting a member never grants consent on their behalf.
        consent_status=ConsentStatus.PENDING,
        privacy_status=PrivacyStatus.PRIVATE_ONLY,
    )
    return {"member": serialize_member(member)}


@router.patch("/{household_id}/members/{member_id}/consent")
def update_member_consent(
    household_id: str,
    member_id: str,
    payload: UpdateMemberConsentRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    member = service.update_member_consent(
        household_id=household_id,
        member_id=member_id,
        requester_member_id=requester_member_id,
        consent_status=ConsentStatus(payload.consentStatus),
    )
    return {"member": serialize_member(member)}


@router.get("/{household_id}/members")
def list_members(household_id: str, service: AccordService = Depends(get_service)) -> dict:
    members = service.list_members(household_id)
    return {"members": [serialize_member(member) for member in members]}
