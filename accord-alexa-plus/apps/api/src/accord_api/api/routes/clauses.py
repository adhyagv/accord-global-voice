from __future__ import annotations

import re
import unicodedata

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...errors import ApiError
from ...models import ConsentStatus, PrivacyClassification
from ...privacy import caller_member_id
from ...services.structured_assistance import (
    AGREEMENT_DRAFTER_SYSTEM_PROMPT,
    basic_conflict_ids,
    fallback_clause,
    optional_json_completion,
)
from ...services.use_cases import AccordService
from ..schemas import DraftAgreementClausesRequest

router = APIRouter(prefix="/agreements", tags=["agreements"])


def _normalize_clause_key(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    normalized = re.sub(r"[^\w\s]", " ", normalized)
    return " ".join(normalized.split())


def _deduplicate_clauses(clauses: list[dict]) -> list[dict]:
    """Remove repeated clause outputs by normalized source preference and text.

    Keep the first occurrence so order remains predictable. IDs remain attached to
    the retained item and conflict references are filtered by the caller.
    """
    seen: set[tuple[str, str]] = set()
    kept: list[dict] = []
    for clause in clauses:
        if not isinstance(clause, dict):
            continue
        key = (_normalize_clause_key(str(clause.get("sourcePreference", ""))), _normalize_clause_key(str(clause.get("text", ""))))
        if not key[0] or not key[1] or key in seen:
            continue
        seen.add(key)
        kept.append(clause)
    return kept


@router.post("/draft-clauses")
async def draft_clauses(
    payload: DraftAgreementClausesRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Draft clauses from shareable derived summaries, never raw private interviews."""
    household = service.get_household(payload.householdId)
    service._require_household_membership(payload.householdId, requester_member_id)
    if any(member.consent_status != ConsentStatus.GRANTED for member in household.members):
        raise ApiError("consent_required", "All household members must have consent granted before drafting shared agreement clauses.", 409)
    eligible = service.list_shareable_constraints(payload.householdId, requester_member_id)
    eligible = [constraint for constraint in eligible if constraint.privacy_classification == PrivacyClassification.SHAREABLE_DERIVED]
    if payload.derivedConstraintIds:
        requested = set(payload.derivedConstraintIds)
        eligible = [constraint for constraint in eligible if constraint.constraint_id in requested]
    if not eligible:
        raise ApiError("missing_constraints", "No permitted shareable derived preferences are available. Complete consented check-ins and derive summaries first.", 400)

    source = [
        {
            "id": constraint.constraint_id,
            "sourceMemberId": constraint.member_id,
            "category": constraint.category,
            "preference": constraint.preference_or_requirement,
        }
        for constraint in eligible
    ]
    fallback_clauses = [
        {
            "id": item["id"],
            "text": fallback_clause(item),
            "sourcePreference": item["preference"],
            "sourceMemberId": item["sourceMemberId"],
            "conflictsWith": [],
            "reviewNote": "Draft only; review this clause with all participating members before accepting it.",
        }
        for item in source
    ]
    fallback_clauses = _deduplicate_clauses(fallback_clauses)
    retained_ids = {clause["id"] for clause in fallback_clauses}
    source = [item for item in source if item["id"] in retained_ids]
    conflict_rows = basic_conflict_ids(source)
    for conflict in conflict_rows:
        left, right = conflict["clauseA"], conflict["clauseB"]
        for clause in fallback_clauses:
            if clause["id"] == left and right not in clause["conflictsWith"]:
                clause["conflictsWith"].append(right)
            elif clause["id"] == right and left not in clause["conflictsWith"]:
                clause["conflictsWith"].append(left)

    result = await optional_json_completion(
        AGREEMENT_DRAFTER_SYSTEM_PROMPT,
        {"householdName": household.name, "shareableDerivedPreferencesOnly": source},
        max_tokens=1200,
    )
    mode = "llm"
    if not result or not isinstance(result.get("clauses"), list):
        result = {"clauses": fallback_clauses, "conflicts": conflict_rows}
        mode = "guided"
    else:
        allowed_ids = {item["id"] for item in source}
        sanitized_clauses = []
        for item in result["clauses"][:100]:
            if not isinstance(item, dict) or item.get("id") not in allowed_ids or not isinstance(item.get("text"), str):
                continue
            original = next(x for x in source if x["id"] == item["id"])
            sanitized_clauses.append({
                "id": original["id"],
                "text": item["text"][:1000],
                "sourcePreference": original["preference"],
                "sourceMemberId": original["sourceMemberId"],
                "conflictsWith": [x for x in item.get("conflictsWith", []) if isinstance(x, str) and x in allowed_ids] if isinstance(item.get("conflictsWith", []), list) else [],
                "reviewNote": str(item.get("reviewNote", "Draft only; review with all participants."))[:300],
            })
        if not sanitized_clauses:
            sanitized_clauses = fallback_clauses
            mode = "guided_fallback"
        sanitized_clauses = _deduplicate_clauses(sanitized_clauses)
        retained_ids = {clause["id"] for clause in sanitized_clauses}
        for clause in sanitized_clauses:
            clause["conflictsWith"] = [item for item in clause["conflictsWith"] if item in retained_ids and item != clause["id"]]
        conflict_output = result.get("conflicts", conflict_rows)
        if isinstance(conflict_output, list):
            conflict_output = [
                {"clauseA": row["clauseA"], "clauseB": row["clauseB"], "reason": str(row.get("reason", "Potentially competing preferences; review together."))[:300]}
                for row in conflict_output
                if isinstance(row, dict) and isinstance(row.get("clauseA"), str) and isinstance(row.get("clauseB"), str)
                and row["clauseA"] in retained_ids and row["clauseB"] in retained_ids
            ]
        else:
            conflict_output = conflict_rows
        result = {"clauses": sanitized_clauses, "conflicts": conflict_output}
    return {
        **result,
        "mode": mode,
        "sourcePolicy": "Only consented shareable derived summaries were used; raw private interview answers were not sent to the drafting model.",
        "status": "draft",
        "requiresMemberReview": True,
        "activatesAgreement": False,
    }
