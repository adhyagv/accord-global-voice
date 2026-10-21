"""Privacy-aware structured assistance with an optional JSON-mode LLM.

The application remains fully usable without a configured provider. Fallbacks
are deterministic and never claim a generative model produced the result.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any

import httpx

MEDIATOR_SYSTEM_PROMPT = """You are a neutral household mediator. You receive only locally derived, non-verbatim need summaries and must never ask for or invent private statements. Restate each need in non-blaming language, identify the shared underlying need, and propose exactly three compromise options with trade-offs. Never take sides, make diagnoses, assign blame, or reveal private details. Return only a JSON object with keys: sharedNeed (string), restatements (array of objects with memberId and needsRestatement), options (array of exactly 3 objects with id, title, proposal, tradeOff, and requiresHouseholdConfirmation=true), cautions (array of strings)."""

FAIRNESS_EXPLAINER_SYSTEM_PROMPT = """Given this allocation result (projected workloads, shareable preferences used, and assigned tasks), write a two-sentence explanation per member of why they received their tasks. Do not expose private statements or private constraints. State plainly that the allocation is a heuristic, not a guarantee of fairness. Return a JSON object with key explanations: an array of {memberId, explanation}. Each explanation must be exactly two sentences."""

AGREEMENT_DRAFTER_SYSTEM_PROMPT = """You draft household agreement clauses in plain, respectful English. Use only the supplied consented, shareable derived preference summaries, never raw private interview answers. Return only a JSON object with keys clauses and conflicts. Each clause object must contain id, text, sourcePreference, sourceMemberId, conflictsWith (array of clause ids), and reviewNote. Identify incompatibilities conservatively rather than inventing conflict. Never claim that a draft has been accepted or activated."""


def provider_status() -> dict[str, Any]:
    """Expose only safe provider readiness metadata; never expose the API key."""
    config = _provider_config()
    if config is None:
        return {"mode": "deterministic", "configured": False, "provider": None, "model": None}
    _, base_url, model = config
    from urllib.parse import urlparse
    return {"mode": "provider", "configured": True, "provider": urlparse(base_url).hostname or "configured provider", "model": model}


def _provider_config() -> tuple[str, str, str] | None:
    key = os.getenv("ACCORD_LLM_API_KEY", "").strip()
    if not key:
        return None
    base_url = os.getenv("ACCORD_LLM_BASE_URL", "https://api.openai.com/v1").strip().rstrip("/")
    model = os.getenv("ACCORD_LLM_MODEL", "gpt-4o-mini").strip() or "gpt-4o-mini"
    if not base_url.startswith(("https://", "http://")):
        return None
    return key, base_url, model


async def optional_json_completion(system_prompt: str, payload: dict[str, Any], *, max_tokens: int = 900) -> dict[str, Any] | None:
    """Request JSON from the configured OpenAI-compatible provider, or return None.

    Failure is intentionally non-fatal; the caller supplies a deterministic fallback.
    Only the caller-approved payload is sent to the provider.
    """
    config = _provider_config()
    if config is None:
        return None
    key, base_url, model = config
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(22.0, connect=5.0)) as client:
            response = await client.post(
                f"{base_url}/chat/completions",
                headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"},
                json={
                    "model": model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
                    ],
                    "response_format": {"type": "json_object"},
                    "temperature": 0.2,
                    "max_tokens": max_tokens,
                },
            )
            response.raise_for_status()
            content = response.json()["choices"][0]["message"]["content"]
            result = json.loads(content)
            return result if isinstance(result, dict) else None
    except (httpx.HTTPError, KeyError, IndexError, TypeError, ValueError):
        return None


def _topic(statement: str) -> str:
    text = statement.casefold()
    if re.search(r"\b(chore|clean|dishes|laundry|trash|kitchen|bathroom|task)\b", text):
        return "chores"
    if re.search(r"\b(bill|money|expense|rent|grocery|payment|budget|cost)\b", text):
        return "money"
    if re.search(r"\b(time|busy|schedule|work|class|availability|weekday|weekend)\b", text):
        return "time"
    if re.search(r"\b(noise|quiet|privacy|space|alone)\b", text):
        return "space"
    return "expectations"


def deterministic_mediation(perspectives: list[dict[str, str]]) -> dict[str, Any]:
    """Create a non-generative need-based fallback without quoting raw statements."""
    topics = [_topic(item["statement"]) for item in perspectives]
    majority = max(set(topics), key=topics.count)
    need_by_topic = {
        "chores": "a predictable, balanced division of household responsibilities",
        "money": "transparent, agreed financial expectations that feel manageable to everyone",
        "time": "a shared plan that respects different schedules and availability",
        "space": "mutual respect for personal space, quiet time, and boundaries",
        "expectations": "clear expectations and a chance for every person to feel heard",
    }
    restatements = []
    for index, item in enumerate(perspectives, start=1):
        topic = _topic(item["statement"])
        restatement = need_by_topic[topic]
        restatements.append({
            "memberId": item["memberId"],
            "label": f"Member {index}",
            "needsRestatement": f"This person needs {restatement}.",
            "privateDetailsOmitted": True,
        })
    shared_need = need_by_topic[majority] if len(set(topics)) == 1 else "a workable agreement that balances clear expectations, individual constraints, and a shared sense of respect"
    options = [
        {
            "id": "rotate-and-review",
            "title": "Rotate responsibilities",
            "proposal": "Distribute the responsibilities using estimated effort, then rotate less-preferred tasks on the next review cycle.",
            "tradeOff": "Easy to understand and share over time, but each rotation still needs to respect genuine availability constraints.",
            "requiresHouseholdConfirmation": True,
        },
        {
            "id": "availability-first",
            "title": "Plan around availability",
            "proposal": "Agree on a shared schedule and assign each responsibility to an available member, balancing effort across the household rather than task count alone.",
            "tradeOff": "More realistic for busy schedules, but it requires members to keep availability information up to date.",
            "requiresHouseholdConfirmation": True,
        },
        {
            "id": "short-trial",
            "title": "Try a one-week agreement",
            "proposal": "Choose a small set of changes for seven days, record what worked, and revisit the arrangement together before making it recurring.",
            "tradeOff": "Low commitment and easy to revise, but it delays a permanent arrangement until after the trial.",
            "requiresHouseholdConfirmation": True,
        },
    ]
    return {
        "sharedNeed": shared_need,
        "restatements": restatements,
        "options": options,
        "cautions": ["This is a guided fallback, not a live LLM response.", "No option is accepted or applied until members confirm it."],
        "mode": "guided",
    }


def fallback_clause(constraint: dict[str, str]) -> str:
    category = constraint.get("category", "preference").replace("_", " ").strip().lower()
    preference = constraint.get("preference", "")
    if category in {"availability", "schedule"}:
        return "Schedule recurring responsibilities around the availability the member has chosen to share, then review the schedule together each week."
    if category in {"expense preference", "budget", "expense"}:
        return "Record shared expenses transparently and confirm the sharing rule before treating a suggested amount as agreed."
    if category in {"task preference", "task preferences", "preference", "rotation"}:
        return "Distribute recurring tasks by estimated effort, permitted preferences, and recent workload; revisit the rotation if it feels unbalanced."
    return f"Review this shared preference together and agree on a practical arrangement: {preference[:220]}"


def basic_conflict_ids(constraints: list[dict[str, str]]) -> list[dict[str, str]]:
    conflicts: list[dict[str, str]] = []
    for i, left in enumerate(constraints):
        left_text = (left.get("preference", "") + " " + left.get("category", "")).casefold()
        for right in constraints[i + 1:]:
            right_text = (right.get("preference", "") + " " + right.get("category", "")).casefold()
            if left.get("sourceMemberId") == right.get("sourceMemberId"):
                continue
            opposing = (
                (("equal" in left_text or "equally" in left_text) and any(t in right_text for t in ("income", "usage", "proportion")))
                or (("income" in left_text or "usage" in left_text or "proportion" in left_text) and ("equal" in right_text or "equally" in right_text))
                or ("weekend" in left_text and "weekday" in right_text)
                or ("weekday" in left_text and "weekend" in right_text)
                or ("quiet" in left_text and "music" in right_text)
                or ("music" in left_text and "quiet" in right_text)
            )
            if opposing:
                conflicts.append({"clauseA": left["id"], "clauseB": right["id"], "reason": "The shared summaries may express competing preferences; ask members to resolve the trade-off."})
    return conflicts
