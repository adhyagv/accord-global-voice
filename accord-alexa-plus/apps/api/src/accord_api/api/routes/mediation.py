from __future__ import annotations

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...errors import ApiError
from ...models import ConsentStatus
from ...privacy import RESOURCE_NOT_FOUND, caller_member_id
from ...services.structured_assistance import (
    MEDIATOR_SYSTEM_PROMPT,
    deterministic_mediation,
    optional_json_completion,
)
from ...services.use_cases import AccordService
from ..schemas import MediationRequest, CreateMediationSessionRequest, CastMediationVoteRequest

router = APIRouter(prefix="/mediation", tags=["mediation"])


@router.post("/propose")
async def propose_mediation(
    payload: MediationRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Create three compromise options from statements explicitly consented to share.

    Inputs are used for this request only and are not stored. The current identity
    header is only a local demo identity, not production authentication.
    """
    household = service.get_household(payload.householdId)
    service._require_household_membership(payload.householdId, requester_member_id)
    household_members = {member.member_id: member for member in household.members}
    approved = []
    for perspective in payload.perspectives:
        member = household_members.get(perspective.memberId)
        if member is None:
            raise RESOURCE_NOT_FOUND
        if member.consent_status != ConsentStatus.GRANTED:
            raise ApiError("consent_required", "Each participating member must have current household consent before sharing a perspective.", 409)
        if not perspective.consentToShare:
            raise ApiError("sharing_consent_required", "Each perspective requires explicit consent to share it for mediation.", 409)
        approved.append({"memberId": perspective.memberId, "statement": perspective.statement})

    # Derive neutral summaries locally. Raw statements never cross the LLM boundary.
    fallback = deterministic_mediation(approved)
    safe_provider_input = {
        "householdContext": "Shared household disagreement; use only these non-verbatim need summaries.",
        "consentedDerivedNeedSummaries": [
            {"memberId": row["memberId"], "needsRestatement": row["needsRestatement"]}
            for row in fallback["restatements"]
        ],
        "sharedNeed": fallback["sharedNeed"],
    }
    result = await optional_json_completion(
        MEDIATOR_SYSTEM_PROMPT, safe_provider_input, max_tokens=1000,
    )
    mode = "llm"
    expected_ids = {item["memberId"] for item in approved}
    raw_restatements = result.get("restatements") if isinstance(result, dict) else None
    valid_restatements = isinstance(raw_restatements, list) and {row.get("memberId") for row in raw_restatements if isinstance(row, dict)} == expected_ids
    valid_options = isinstance(result, dict) and isinstance(result.get("options"), list) and len(result["options"]) == 3 and all(
        isinstance(option, dict)
        and all(isinstance(option.get(key), str) and option[key].strip() for key in ("title", "proposal", "tradeOff"))
        for option in result["options"]
    )
    if not result or not isinstance(result.get("sharedNeed"), str) or not valid_restatements or not valid_options:
        result = fallback
        mode = "guided"
    else:
        safe_restatements = []
        for index, perspective in enumerate(approved, start=1):
            row = next(row for row in raw_restatements if row["memberId"] == perspective["memberId"])
            safe_restatements.append({
                "memberId": perspective["memberId"],
                "label": f"Member {index}",
                "needsRestatement": str(row.get("needsRestatement", "")).strip()[:600],
                "privateDetailsOmitted": True,
            })
        # Do not allow the model to turn a suggestion into an automatic action.
        safe_options = []
        for index, option in enumerate(result["options"], start=1):
            safe_options.append({
                "id": f"option-{index}",
                "title": option["title"].strip()[:120],
                "proposal": option["proposal"].strip()[:900],
                "tradeOff": option["tradeOff"].strip()[:700],
                "requiresHouseholdConfirmation": True,
            })
        result = {
            "sharedNeed": str(result["sharedNeed"]).strip()[:600],
            "restatements": safe_restatements,
            "options": safe_options,
            "cautions": [str(caution)[:300] for caution in result.get("cautions", []) if isinstance(caution, str)][:6],
        }
    result["mode"] = mode
    result["requiresConfirmationBeforeAction"] = True
    result["stored"] = False
    result["privacyNote"] = "Raw statements were processed locally into neutral need summaries and were not sent to an LLM or stored. Only those derived summaries and options may be saved in a mediation session; review them before sharing."
    return result


@router.post("/sessions", status_code=201)
def create_mediation_session(
    payload: CreateMediationSessionRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Persist safe mediation summaries/options only; request schemas exclude raw statements."""
    from datetime import UTC, datetime
    from ...models import MediationSession

    household = service.get_household(payload.householdId)
    service._require_household_membership(payload.householdId, requester_member_id)
    members = {member.member_id: member for member in household.members}
    for row in payload.restatements:
        member = members.get(row.memberId)
        if member is None:
            raise RESOURCE_NOT_FOUND
        if member.consent_status != ConsentStatus.GRANTED:
            raise ApiError("consent_required", "Only currently consenting members may appear in a shared mediation session.", 409)
    session_id = service.ctx.id_gen.next("mediation-session")
    session = MediationSession(
        session_id=session_id,
        household_id=payload.householdId,
        topic=payload.topic.strip()[:160],
        restatements=[{
            "memberId": row.memberId,
            "label": row.label,
            "needsRestatement": row.needsRestatement.strip()[:600],
            "privateDetailsOmitted": True,
        } for row in payload.restatements],
        options=[{
            "id": option.id,
            "title": option.title.strip()[:120],
            "proposal": option.proposal.strip()[:900],
            "tradeOff": option.tradeOff.strip()[:700],
            "requiresHouseholdConfirmation": True,
        } for option in payload.options],
        created_at=datetime.now(UTC),
    )
    service.ctx.mediation_sessions[session_id] = session
    return {"session": _serialize_mediation_session(session)}


def _serialize_mediation_session(session) -> dict:
    vote_counts = {option["id"]: 0 for option in session.options}
    for option_id in session.votes.values():
        if option_id in vote_counts:
            vote_counts[option_id] += 1
    return {
        "sessionId": session.session_id,
        "householdId": session.household_id,
        "topic": session.topic,
        "status": session.status,
        "restatements": session.restatements,
        "options": session.options,
        "votes": dict(session.votes),
        "voteCounts": vote_counts,
        "winningOptionId": session.winning_option_id,
        "tie": session.tie,
        "tieBreakRule": session.tie_break_rule,
        "draftAgreementId": session.draft_agreement_id,
        "createdAt": session.created_at.isoformat(),
        "closedAt": session.closed_at.isoformat() if session.closed_at else None,
        "storedFields": ["neutral restatements", "options", "member votes", "status"],
        "storedRawPrivateStatements": False,
    }


@router.get("/sessions/{session_id}")
def get_mediation_session(
    session_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    session = service.ctx.mediation_sessions.get(session_id)
    if session is None:
        raise RESOURCE_NOT_FOUND
    service._require_household_membership(session.household_id, requester_member_id)
    return {"session": _serialize_mediation_session(session)}


@router.post("/sessions/{session_id}/vote")
def cast_mediation_vote(
    session_id: str,
    payload: CastMediationVoteRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    session = service.ctx.mediation_sessions.get(session_id)
    if session is None:
        raise RESOURCE_NOT_FOUND
    service._require_household_membership(session.household_id, requester_member_id)
    household = service.get_household(session.household_id)
    members = {member.member_id: member for member in household.members}
    member = members.get(requester_member_id)
    if member is None:
        raise RESOURCE_NOT_FOUND
    if member.consent_status != ConsentStatus.GRANTED:
        raise ApiError("consent_required", "Only currently consenting members can vote in this mediation session.", 409)
    if session.status != "open":
        raise ApiError("session_closed", "Voting is closed for this mediation session.", 409)
    if payload.optionId not in {option["id"] for option in session.options}:
        raise ApiError("unknown_option", "Choose one of the options shown in this session.", 422)
    previous = session.votes.get(requester_member_id)
    session.votes[requester_member_id] = payload.optionId
    service.ctx.mediation_sessions[session_id] = session
    return {"session": _serialize_mediation_session(session), "voteChanged": previous is not None and previous != payload.optionId}


@router.post("/sessions/{session_id}/close")
def close_mediation_session(
    session_id: str,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    from datetime import UTC, datetime
    from ...models import AgreementStatus, AgreementVersion

    session = service.ctx.mediation_sessions.get(session_id)
    if session is None:
        raise RESOURCE_NOT_FOUND
    service._require_household_membership(session.household_id, requester_member_id)
    if session.status == "closed":
        return {"session": _serialize_mediation_session(session), "agreement": _serialize_draft_agreement(service, session)}
    household = service.get_household(session.household_id)
    consenting_ids = {member.member_id for member in household.members if member.consent_status == ConsentStatus.GRANTED}
    if not consenting_ids.issubset(set(session.votes)):
        missing = sorted(consenting_ids - set(session.votes))
        raise ApiError("votes_pending", f"All currently consenting household members must vote before closing. Pending: {', '.join(missing)}", 409)
    if not session.votes:
        raise ApiError("no_votes", "At least one vote is required before closing the session.", 409)
    counts = {option["id"]: 0 for option in session.options}
    for option_id in session.votes.values():
        counts[option_id] = counts.get(option_id, 0) + 1
    highest = max(counts.values())
    tied_ids = {option_id for option_id, count in counts.items() if count == highest}
    winner = next(option for option in session.options if option["id"] in tied_ids)
    session.winning_option_id = winner["id"]
    session.tie = len(tied_ids) > 1
    session.status = "closed"
    session.closed_at = datetime.now(UTC)
    agreement = AgreementVersion(
        agreement_id=service.ctx.id_gen.next("agreement"),
        household_id=session.household_id,
        version=1,
        status=AgreementStatus.DRAFT,
        proposal=[],
        fairness_score=0.0,
        rationale=(
            f"Mediation vote draft: {winner['title']}. {winner['proposal']} "
            f"Trade-off: {winner['tradeOff']} This is a draft counteroffer created from a household vote; "
            "members must submit it through the existing agreement approval workflow before it can become active."
            + (f" A tie was resolved using the documented rule: {session.tie_break_rule}" if session.tie else "")
        ),
        created_at=datetime.now(UTC),
    )
    service.ctx.agreements.create(agreement)
    session.draft_agreement_id = agreement.agreement_id
    service.ctx.mediation_sessions[session_id] = session
    return {"session": _serialize_mediation_session(session), "agreement": {"agreementId": agreement.agreement_id, "version": agreement.version, "status": agreement.status.value, "rationale": agreement.rationale}}


def _serialize_draft_agreement(service: AccordService, session) -> dict | None:
    if not session.draft_agreement_id:
        return None
    versions = service.ctx.agreements.list_versions(session.draft_agreement_id)
    if not versions:
        return None
    agreement = versions[-1]
    return {"agreementId": agreement.agreement_id, "version": agreement.version, "status": agreement.status.value, "rationale": agreement.rationale}
