from __future__ import annotations

from fastapi import APIRouter

from ...services.structured_assistance import provider_status

router = APIRouter(prefix="/privacy", tags=["privacy dashboard"])


@router.get("/dashboard")
def privacy_dashboard() -> dict:
    """Describe real provider readiness and the data boundaries enforced by this prototype."""
    status = provider_status()
    return {
        "llmMode": status["mode"],
        "providerConfigured": status["configured"],
        "provider": status["provider"],
        "model": status["model"],
        "canSee": [
            "The current chat message submitted to the assistant endpoint.",
            "Consented, shareable derived need summaries created locally from explicitly shared mediation inputs.",
            "Consented shareable derived constraints needed for fairness explanations and agreement clause drafting.",
            "Aggregated household task, expense and agreement records used for on-demand weekly digests; digests are not sent to an LLM.",
        ],
        "cannotSee": [
            "Raw private interview answers are never sent to an LLM or fairness solver.",
            "Constraints classified private are excluded from fairness and clause drafting.",
            "Raw mediation statements are locally reduced to neutral need summaries before any optional LLM call.",
            "Voice playback uses browser speech synthesis and does not upload a separate audio recording.",
        ],
        "identityNote": "X-Member-Id is a local demo identity header, not production authentication.",
        "limitations": [
            "This prototype does not implement production-grade account authentication or multi-tenant authorization.",
            "A configured provider receives only the specific sanitized payload described by each endpoint, not the whole household database.",
        ],
    }
