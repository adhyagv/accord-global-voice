from __future__ import annotations

import os
import sys
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ["ACCORD_PERSISTENCE"] = "memory"
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from accord_api.app import create_app  # noqa: E402


def test_assistant_status_reports_guided_mode_without_secret() -> None:
    client = TestClient(create_app())
    response = client.get("/api/assistant/status")
    assert response.status_code == 200
    assert response.json()["mode"] in {"guided", "configured"}
    assert "api_key" not in response.json()


def test_guided_assistant_suggests_real_workflow_without_mutating_data(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    client = TestClient(create_app())
    response = client.post("/api/assistant/chat", json={"message": "Help me create chores"})
    assert response.status_code == 200
    body = response.json()
    assert body["mode"] == "guided"
    assert body["suggestedAction"] == "chores"
    assert "Open Chores" in body["reply"]
    assert "tasks" in body["reply"].lower()


def test_conflict_intent_takes_priority_over_task_keywords(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    client = TestClient(create_app())
    response = client.post("/api/assistant/chat", json={"message": "We keep arguing about chores"})
    assert response.status_code == 200
    assert response.json()["suggestedAction"] == "mediation"
    assert "private check-ins" in response.json()["reply"].lower()


def test_configured_but_invalid_provider_uses_safe_guided_fallback(monkeypatch) -> None:
    monkeypatch.setenv("ACCORD_LLM_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("ACCORD_LLM_BASE_URL", "file:///not-a-provider")
    client = TestClient(create_app())
    response = client.post("/api/assistant/chat", json={"message": "help with the weekly plan"})
    assert response.status_code == 200
    assert response.json()["mode"] == "guided_fallback"
    assert response.json()["suggestedAction"] == "plan"


def test_assistant_rejects_blank_or_oversized_messages(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    client = TestClient(create_app())
    assert client.post("/api/assistant/chat", json={"message": "   "}).status_code == 422
    assert client.post("/api/assistant/chat", json={"message": "x" * 2001}).status_code == 422


def test_agreement_request_routes_to_review_workflow(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    client = TestClient(create_app())
    response = client.post("/api/assistant/chat", json={"message": "Can we review the agreement and approve the proposal?"})
    assert response.status_code == 200
    body = response.json()
    assert body["suggestedAction"] == "agreements"
    assert "review the proposal" in body["reply"].lower()


def test_agreement_intent_does_not_get_swallowed_by_generic_chore_intent(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    client = TestClient(create_app())
    response = client.post("/api/assistant/chat", json={"message": "Can we review the agreement and approve the proposal?"})
    assert response.status_code == 200
    assert response.json()["suggestedAction"] == "agreements"
