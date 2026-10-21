from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...privacy import caller_member_id
from ...serializers import serialize_expense
from ...services.use_cases import AccordService
from ..schemas import CreateExpenseRequest

router = APIRouter(prefix="/expenses", tags=["expenses"])


@router.post("", status_code=201)
def create_expense(
    payload: CreateExpenseRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    expense = service.create_expense(
        household_id=payload.householdId,
        requester_member_id=requester_member_id,
        payer_member_id=payload.payerMemberId,
        description=payload.description,
        amount=payload.amount,
        category=payload.category,
        expense_date=payload.expenseDate,
        split_member_ids=payload.splitMemberIds,
        split_ratios=payload.splitRatios,
    )
    return {"expense": serialize_expense(expense)}


@router.get("/households/{household_id}/settle-up")
def settle_up(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Return split-aware, net-zero reimbursement suggestions; no money is transferred."""
    return service.calculate_settle_up(household_id, requester_member_id)


@router.get("/households/{household_id}")
def list_expenses(
    household_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    expenses = service.list_expenses(household_id, requester_member_id)
    return {"expenses": [serialize_expense(item) for item in expenses]}
