"""Optional AI-assisted conversational support with a safe guided fallback.

The assistant receives only the user's current message. It is not sent private
interview data and cannot mutate household records. It may suggest a workflow;
consequential changes still require explicit user action through existing APIs.
"""

from __future__ import annotations

import os
import re
import time
import threading
from collections import defaultdict, deque

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field, field_validator

from ...errors import ApiError
from ...dependencies import get_service
from ...privacy import caller_member_id
from ...services.use_cases import AccordService
from ..schemas import WeeklyMealPlanRequest

router = APIRouter(prefix="/assistant", tags=["assistant"])
_RATE_LOCK = threading.Lock()
_RATE_HITS: dict[str, deque[float]] = defaultdict(deque)
_RATE_WINDOW_SECONDS = 60.0


def _enforce_chat_rate_limit(client_key: str, *, now: float | None = None) -> None:
    """Small per-client process-local limit for the local prototype."""
    try:
        limit = int(os.getenv("ACCORD_ASSISTANT_RATE_LIMIT_PER_MIN", "60"))
    except ValueError:
        limit = 60
    limit = max(1, min(limit, 600))
    moment = time.monotonic() if now is None else now
    with _RATE_LOCK:
        hits = _RATE_HITS[client_key]
        while hits and moment - hits[0] >= _RATE_WINDOW_SECONDS:
            hits.popleft()
        if len(hits) >= limit:
            raise ApiError("assistant_rate_limited", "Too many assistant requests. Wait a minute and try again.", 429)
        hits.append(moment)
        # Bound memory use even if many short-lived client IPs contact the app.
        if len(_RATE_HITS) > 2000:
            for stale_key in list(_RATE_HITS)[:500]:
                if stale_key != client_key and not _RATE_HITS[stale_key]:
                    _RATE_HITS.pop(stale_key, None)

_SYSTEM_PROMPT = """You are Accord, a calm, privacy-first household diplomat. Help people who share a home make practical, voluntary plans and resolve disagreements without taking sides. Be warm, specific, concise, and non-judgmental. Never claim you changed tasks, recorded expenses, contacted anyone, read private interviews, or activated an agreement. You receive only the current message and must not invent household facts. For consequential changes, direct the user to review the relevant Accord workflow. Encourage explicit consent and voluntary agreement. Do not pressure anyone to participate. If key details are missing, ask one focused follow-up question. Keep responses under 180 words."""


class AssistantChatRequest(BaseModel):
    message: str = Field(min_length=1, max_length=2000)

    @field_validator("message", mode="before")
    @classmethod
    def trim_and_require_message(cls, value: object) -> object:
        if isinstance(value, str):
            value = value.strip()
            if not value:
                raise ValueError("message must not be blank")
        return value


def _suggest_action(message: str) -> str:
    text = message.casefold()
    rules: tuple[tuple[str, tuple[str, ...]], ...] = (
        # Conflict language wins over topic words so “we argue about chores”
        # routes to mediation rather than only opening the task list.
        ("mediation", ("fight", "argue", "arguing", "argument", "disagree", "conflict", "unfair", "upset", "mediate", "listen to everyone")),
        ("agreements", ("agreement", "proposal", "approve", "approval", "counteroffer", "counter offer", "fair plan", "decision", "decisions")),
        ("chores", ("chore", "chores", "clean", "laundry", "trash", "vacuum", "dishes", "task", "assignment")),
        ("bills", ("bill", "expense", "rent", "electricity", "internet", "grocery", "budget", "payment", "cost")),
        ("monitoring", ("monitor", "imbalance", "drift", "renegotiate", "household balance")),
        ("meals", ("meal plan", "meals", "dinner plan", "who cooks", "cook this week")),
        ("plan", ("plan", "week", "schedule", "routine", "meal", "calendar")),
        ("household", ("member", "family", "roommate", "partner", "sibling", "parent", "household")),
    )
    for action, terms in rules:
        if any(re.search(rf"\b{re.escape(term)}\b", text) for term in terms):
            return action
    return "none"


def _guided_reply(message: str, action: str) -> str:
    responses = {
        "chores": "Let's make the workload visible first. Open Chores to review existing tasks, create a new task, or update its status. A fair rotation should account for effort and availability, not just task count.",
        "bills": "Let's make shared spending transparent. Open Bills to review recorded expenses or add a new entry. Accord can calculate suggested shares, but it will not claim a payment happened unless a payment provider is actually connected.",
        "mediation": "We can slow this down and hear each person's perspective without taking sides. Private check-ins are optional; only permitted derived summaries should inform a shared proposal. Open Private check-in to begin after checking consent.",
        "agreements": "Let's review the proposal before anyone commits. Open Fair plan & decisions to compare the rationale, approvals, requests for changes, and counteroffers. A plan should become active only through the backend's required approval flow.",
        "monitoring": "Let's review how the current arrangement is going. Open Household balance to inspect the prototype's monitoring signals and decide whether a voluntary check-in is useful. Signals in this demo are simulated, not live sensors.",
        "meals": "I can prepare a seven-day meal rotation draft using only consented, shareable preferences and availability. It will not be saved until the household confirms it.",
        "plan": "Let's make the week practical. Open Plans to review the current tasks and schedule, then use Chores to create or update responsibilities. Accord's suggestions are not saved until you confirm an action in the relevant workflow.",
        "household": "Open My Household to review members, roles and each person's consent. New members start with consent pending; adding someone does not grant consent on their behalf.",
        "none": "I can help you plan routines, balance chores, track shared expenses, review agreements, or talk through a disagreement. Tell me which part of home life feels hardest right now, and we'll take one step at a time.",
    }
    return responses[action]


@router.get("/status")
def assistant_status() -> dict:
    """Return provider readiness without exposing secrets or configuration values."""
    configured = bool(os.getenv("ACCORD_LLM_API_KEY", "").strip())
    return {
        "configured": configured,
        "mode": "configured" if configured else "guided",
        "message": "Optional LLM provider is configured." if configured else "Guided assistant is ready. Configure an optional OpenAI-compatible provider to enable generative replies.",
    }


@router.post("/chat")
async def assistant_chat(payload: AssistantChatRequest, request: Request) -> dict:
    """Answer one message; do not include household records or perform mutations."""
    client_key = request.client.host if request.client else "unknown-client"
    _enforce_chat_rate_limit(client_key)
    message = payload.message.strip()
    if not message:
        # Pydantic min_length catches an empty string, while this covers whitespace.
        return {"reply": _guided_reply(message, "none"), "mode": "guided", "suggestedAction": "none"}

    action = _suggest_action(message)
    fallback = _guided_reply(message, action)
    api_key = os.getenv("ACCORD_LLM_API_KEY", "").strip()
    if not api_key:
        return {"reply": fallback, "mode": "guided", "suggestedAction": action}

    base_url = os.getenv("ACCORD_LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.getenv("ACCORD_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not base_url.startswith(("https://", "http://")):
        return {"reply": fallback, "mode": "guided_fallback", "suggestedAction": action}

    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(18.0, connect=5.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": _SYSTEM_PROMPT},
                        {"role": "user", "content": message},
                    ],
                    "temperature": 0.4,
                    "max_tokens": 260,
                },
            )
            response.raise_for_status()
            result = response.json()
            reply = result["choices"][0]["message"]["content"]
            if not isinstance(reply, str) or not reply.strip():
                raise ValueError("empty_assistant_response")
            return {"reply": reply.strip()[:3000], "mode": "llm", "suggestedAction": action}
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        # Do not expose provider errors, request headers or secrets to the browser.
        return {"reply": fallback, "mode": "guided_fallback", "suggestedAction": action}


@router.post("/meal-plan")
def create_meal_plan_draft(
    payload: WeeklyMealPlanRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Create a deterministic seven-day meal rota from shareable data only; no writes."""
    from datetime import date, timedelta

    household = service.get_household(payload.householdId)
    service._require_household_membership(payload.householdId, requester_member_id)
    members = [m for m in service.ctx.members.list_by_household(payload.householdId) if m.consent_status.value == "granted"]
    if not members:
        raise ApiError("no_consenting_members", "No currently consenting members are available for a meal plan.", 409)
    constraints = service.list_shareable_constraints(payload.householdId, requester_member_id)
    # Deliberately filter again by explicit shareable classification and relevant fields.
    safe_constraints = [c for c in constraints if c.privacy_classification.value == "shareable_derived" and c.category.casefold() in {"availability", "schedule", "meal", "meal_preference", "task_preference", "task_preferences", "preference"}]
    cooking_count = {m.member_id: 0 for m in members}
    day_names = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"]
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    meals = ["Simple rice bowl", "Pasta or noodles", "Vegetable curry", "Wraps or sandwiches", "One-pot meal", "Leftovers / flexible meal", "Shared favourite"]
    schedule: list[dict[str, object]] = []
    for idx in range(7):
        day = monday + timedelta(days=idx)
        day_constraints = [c for c in safe_constraints if c.member_id in cooking_count]
        unavailable_ids: set[str] = set()
        for c in day_constraints:
            text = c.preference_or_requirement.casefold()
            if "unavailable" in text or "cannot cook" in text or "not available" in text:
                if day.weekday() < 5 and any(term in text for term in ("weekday", day_names[idx].casefold())):
                    unavailable_ids.add(c.member_id)
                if day_names[idx].casefold() in text:
                    unavailable_ids.add(c.member_id)
        available = [m for m in members if m.member_id not in unavailable_ids] or members
        def preference_cost(member):
            score = cooking_count[member.member_id] * 100
            for c in day_constraints:
                if c.member_id != member.member_id:
                    continue
                text = c.preference_or_requirement.casefold()
                if "cook" in text and any(term in text for term in ("prefer", "likes", "enjoy")):
                    score -= 5 * max(0.0, min(1.0, float(c.importance_weight)))
                if "cook" in text and any(term in text for term in ("avoid", "dislike", "cannot")):
                    score += 5 * max(0.0, min(1.0, float(c.importance_weight)))
            return score, member.member_id
        cook = min(available, key=preference_cost)
        cooking_count[cook.member_id] += 1
        schedule.append({"date": day.isoformat(), "day": day_names[idx], "mealIdea": meals[idx], "cookMemberId": cook.member_id, "cookDisplayName": cook.display_name})
    return {
        "householdId": household.household_id,
        "householdName": household.name,
        "schedule": schedule,
        "status": "draft",
        "saved": False,
        "requiresHouseholdConfirmation": True,
        "shareableDataOnly": True,
        "constraintsUsed": len(safe_constraints),
        "note": "Deterministic meal rota draft based only on currently consented members and shareable availability/preferences. No private answers were read, no assignment was written, and the household must confirm before saving.",
    }
