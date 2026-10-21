"""Alexa Skills Kit request/response adapter for the Accord demo.

This endpoint implements the core request envelope for local integration tests.
It is not safe to publish directly: production Alexa signature/timestamp
verification, account linking and household authorization must be added first.
"""
from __future__ import annotations

from typing import Any
import hmac
import os

from fastapi import APIRouter, Header
from ...errors import ApiError

router = APIRouter(prefix="/alexa", tags=["Alexa skill adapter (demo)"])


def _speech(text: str, *, should_end: bool = False, reprompt: str | None = None) -> dict[str, Any]:
    response: dict[str, Any] = {
        "version": "1.0",
        "response": {
            "outputSpeech": {"type": "PlainText", "text": text},
            "shouldEndSession": should_end,
        },
    }
    if reprompt and not should_end:
        response["response"]["reprompt"] = {"outputSpeech": {"type": "PlainText", "text": reprompt}}
    return response


@router.post("/skill-request")
def handle_alexa_skill_request(
    payload: dict[str, Any],
    x_accord_alexa_secret: str | None = Header(default=None, alias="X-Accord-Alexa-Secret"),
) -> dict[str, Any]:
    """Prototype Skills Kit adapter, disabled by default.

    When enabled locally, a shared-secret header is required as a temporary guard.
    This is NOT Amazon request-signature verification and is not production security.
    """
    enabled = os.getenv("ACCORD_ALEXA_ENABLED", "false").strip().casefold() in {"1", "true", "yes", "on"}
    if not enabled:
        raise ApiError("alexa_adapter_disabled", "The Alexa adapter is disabled by default. Enable it only for a controlled local integration test.", 503)
    expected_secret = os.getenv("ACCORD_ALEXA_SHARED_SECRET", "").strip()
    if not expected_secret or not x_accord_alexa_secret or not hmac.compare_digest(x_accord_alexa_secret, expected_secret):
        raise ApiError("alexa_adapter_unauthorized", "A valid X-Accord-Alexa-Secret header is required for this prototype adapter.", 401)
    request = payload.get("request") or {}
    request_type = request.get("type")
    if request_type == "LaunchRequest":
        return _speech(
            "Welcome to Accord. I can help you plan chores, understand a shared household issue, or review an agreement. What would you like to do?",
            reprompt="You can say, ask Accord for help.",
        )
    if request_type == "SessionEndedRequest":
        return {"version": "1.0", "response": {"shouldEndSession": True}}
    if request_type != "IntentRequest":
        return _speech("I couldn't understand that Accord request. Please try again.", reprompt="Say, ask Accord for help.")

    intent = ((request.get("intent") or {}).get("name") or "").strip()
    if intent in {"AccordHelpIntent", "AMAZON.HelpIntent"}:
        return _speech(
            "Accord helps households organize chores, review shared expenses, and discuss disagreements respectfully. For privacy, private check-ins or approving an agreement must happen in the Accord app so everyone can review and consent.",
            reprompt="You can say, what can Accord help with?",
        )
    if intent in {"HouseholdPlanIntent", "PlanMyWeekIntent"}:
        return _speech(
            "Let's plan a calmer week. In the Accord app, review available members and tasks, then compare the workload-aware plan with the simple rotation. No plan is applied until household members review it.",
            reprompt="Would you like help with chores, expenses, or a disagreement?",
        )
    if intent in {"ResolveDisagreementIntent", "MediationHelpIntent"}:
        return _speech(
            "I can help you approach the disagreement neutrally. Open the Accord app to submit perspectives only after each participant explicitly agrees to share them. No private check-in will be read aloud.",
            reprompt="Say, help me plan the week, or open Accord for a private check-in.",
        )
    if intent in {"AMAZON.StopIntent", "AMAZON.CancelIntent", "AMAZON.FallbackIntent"}:
        if intent == "AMAZON.FallbackIntent":
            return _speech("I can help with household planning and neutral conflict guidance. For agreements and private details, please use the Accord app.", reprompt="Say, ask Accord for help.")
        return _speech("Okay. Accord is here whenever your household needs it.", should_end=True)
    return _speech("I don't recognize that Accord intent yet. Please open the Accord app for the full household workspace.", reprompt="Try asking Accord for help.")
