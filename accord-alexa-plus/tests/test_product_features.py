from __future__ import annotations

import os
import sys
from pathlib import Path
from datetime import UTC, datetime

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ["ACCORD_PERSISTENCE"] = "memory"
os.environ.pop("ACCORD_LLM_API_KEY", None)
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from accord_api.app import create_app  # noqa: E402
from accord_api.dependencies import get_context  # noqa: E402


def seed_household(client: TestClient) -> tuple[str, list[str]]:
    created = client.post("/api/households", json={"name": "Willow House", "scenarioMetadata": {"mode": "test"}})
    assert created.status_code == 201
    household_id = created.json()["household"]["householdId"]
    member_ids = []
    for name in ("Priya", "Rahul", "Aman"):
        member = client.post(f"/api/households/{household_id}/members", json={"displayName": name, "role": "roommate"}).json()["member"]
        member_id = member["memberId"]
        consent = client.patch(f"/api/households/{household_id}/members/{member_id}/consent", headers={"X-Member-Id": member_id}, json={"consentStatus": "granted"})
        assert consent.status_code == 200
        member_ids.append(member_id)
    return household_id, member_ids


def test_fairness_comparison_includes_round_robin_and_is_read_only() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    response = client.post(
        "/api/fairness/compare",
        headers={"X-Member-Id": member_ids[0]},
        json={"householdId": household_id, "preferenceWeight": 0.8, "tasks": [{"task": "Dishes", "estimatedEffort": 30}, {"task": "Bathroom", "estimatedEffort": 45}]},
    )
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["solver"]["algorithm"] == "Accord workload-aware solver"
    assert body["roundRobin"]["algorithm"] == "Round-robin baseline"
    assert len(body["solver"]["assignments"]) == 2
    assert len(body["solver"]["workloads"]) == 3
    assert "heuristic" in body["note"].lower()
    assert len(client.get(f"/api/assignments/households/{household_id}", headers={"X-Member-Id": member_ids[0]}).json()["assignments"]) == 0


def test_mediation_requires_explicit_consented_perspectives_and_returns_three_options() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    payload = {
        "householdId": household_id,
        "perspectives": [
            {"memberId": member_ids[0], "statement": "I feel I clean the kitchen every day and need a better rotation.", "consentToShare": True},
            {"memberId": member_ids[1], "statement": "I am busy on weekdays and need the schedule to account for my class time.", "consentToShare": True},
        ],
    }
    response = client.post("/api/mediation/propose", headers={"X-Member-Id": member_ids[0]}, json=payload)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["options"]) == 3
    assert body["requiresConfirmationBeforeAction"] is True
    assert body["stored"] is False
    assert body["mode"] == "guided"
    assert all("needsRestatement" in row for row in body["restatements"])

    payload["perspectives"][1]["consentToShare"] = False
    rejected = client.post("/api/mediation/propose", headers={"X-Member-Id": member_ids[0]}, json=payload)
    assert rejected.status_code == 422


def test_draft_clauses_uses_shareable_summaries_only() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    constraint_ids = []
    for member_id in member_ids:
        session = client.post("/api/interviews", json={"householdId": household_id, "memberId": member_id}).json()["session"]
        assert client.post(f"/api/interviews/{session['sessionId']}/submit", headers={"X-Member-Id": member_id}, json={"transcriptReference": "private://test", "answers": {"chores": "I prefer a balanced kitchen rotation"}}).status_code == 200
        assert client.post(f"/api/interviews/{session['sessionId']}/complete", headers={"X-Member-Id": member_id}).status_code == 200
        constraints = client.post(f"/api/constraints/derive/{session['sessionId']}", headers={"X-Member-Id": member_id}).json()["constraints"]
        constraint_ids.extend(c["constraintId"] for c in constraints if c["privacyClassification"] == "shareable_derived")
    response = client.post("/api/agreements/draft-clauses", headers={"X-Member-Id": member_ids[0]}, json={"householdId": household_id, "derivedConstraintIds": constraint_ids})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["status"] == "draft"
    assert body["requiresMemberReview"] is True
    assert body["activatesAgreement"] is False
    assert body["clauses"]
    assert "raw private interview answers were not sent" in body["sourcePolicy"]


def test_settle_up_optimizes_equal_split_reimbursements_without_payment() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    now = datetime.now(UTC).isoformat()
    for payer_id, amount, description in [(member_ids[0], 300, "Groceries"), (member_ids[1], 150, "Utilities")]:
        result = client.post("/api/expenses", headers={"X-Member-Id": member_ids[0]}, json={"householdId": household_id, "payerMemberId": payer_id, "description": description, "amount": amount, "category": "shared", "expenseDate": now})
        assert result.status_code == 201, result.text
    response = client.get(f"/api/expenses/households/{household_id}/settle-up", headers={"X-Member-Id": member_ids[0]})
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["totalExpenses"] == 450.0
    assert body["memberCount"] == 3
    assert body["transfers"] == [{"fromMemberId": member_ids[2], "toMemberId": member_ids[0], "amount": 150.0}]
    assert "No payment has been initiated" in body["note"]


def test_weekly_digest_and_alexa_adapter_are_available() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    digest = client.get(f"/api/monitoring/weekly-digest/{household_id}", headers={"X-Member-Id": member_ids[0]})
    assert digest.status_code == 200, digest.text
    assert digest.json()["windowDays"] == 7
    assert "insights" in digest.json()

    alexa_payload = {"version": "1.0", "request": {"type": "IntentRequest", "intent": {"name": "AccordHelpIntent"}}}
    disabled = client.post("/api/alexa/skill-request", json=alexa_payload)
    assert disabled.status_code == 503
    import os
    os.environ["ACCORD_ALEXA_ENABLED"] = "true"
    os.environ["ACCORD_ALEXA_SHARED_SECRET"] = "test-secret"
    try:
        missing_secret = client.post("/api/alexa/skill-request", json=alexa_payload)
        assert missing_secret.status_code == 401
        alexa = client.post("/api/alexa/skill-request", headers={"X-Accord-Alexa-Secret": "test-secret"}, json=alexa_payload)
        assert alexa.status_code == 200, alexa.text
        assert "response" in alexa.json()
        assert "privacy" in alexa.json()["response"]["outputSpeech"]["text"].lower()
    finally:
        os.environ.pop("ACCORD_ALEXA_ENABLED", None)
        os.environ.pop("ACCORD_ALEXA_SHARED_SECRET", None)
