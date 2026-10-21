from __future__ import annotations

import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
os.environ["ACCORD_PERSISTENCE"] = "memory"
os.environ.pop("ACCORD_LLM_API_KEY", None)
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "sim" / "src"))

from accord_api.app import create_app  # noqa: E402
from accord_api.dependencies import get_context  # noqa: E402
from accord_api.api.routes.clauses import _deduplicate_clauses  # noqa: E402
from accord_api.api.routes.assistant import _RATE_HITS, _RATE_LOCK  # noqa: E402
from accord_api.services.context import build_context  # noqa: E402


def seed_household(client: TestClient) -> tuple[str, list[str]]:
    response = client.post("/api/households", json={"name": "Willow House", "scenarioMetadata": {"mode": "test"}})
    assert response.status_code == 201, response.text
    household_id = response.json()["household"]["householdId"]
    member_ids = []
    for name in ("Priya", "Rahul", "Aman"):
        response = client.post(f"/api/households/{household_id}/members", json={"displayName": name, "role": "roommate"})
        member_id = response.json()["member"]["memberId"]
        assert client.patch(f"/api/households/{household_id}/members/{member_id}/consent", headers={"X-Member-Id": member_id}, json={"consentStatus": "granted"}).status_code == 200
        member_ids.append(member_id)
    return household_id, member_ids


def make_session_payload(household_id: str, member_ids: list[str]) -> dict:
    return {
        "householdId": household_id,
        "topic": "Kitchen and weekly chores",
        "restatements": [
            {"memberId": member_ids[0], "label": "Member 1", "needsRestatement": "This person needs a predictable and balanced rotation.", "privateDetailsOmitted": True},
            {"memberId": member_ids[1], "label": "Member 2", "needsRestatement": "This person needs the schedule to respect availability.", "privateDetailsOmitted": True},
        ],
        "options": [
            {"id": "option-1", "title": "Rotate duties", "proposal": "Rotate the kitchen duties weekly.", "tradeOff": "Requires a weekly review."},
            {"id": "option-2", "title": "Availability first", "proposal": "Schedule duties around shared availability.", "tradeOff": "Needs availability updates."},
            {"id": "option-3", "title": "One-week trial", "proposal": "Try a one-week plan and review it.", "tradeOff": "Permanent changes wait until review."},
        ],
    }


def test_clause_deduplication_normalizes_preference_and_text() -> None:
    result = _deduplicate_clauses([
        {"id": "a", "sourcePreference": "Prefer cooking!", "text": "Rotate chores, fairly."},
        {"id": "b", "sourcePreference": "  PREFER COOKING ", "text": "rotate chores fairly"},
        {"id": "c", "sourcePreference": "Prefer cooking", "text": "Rotate chores monthly"},
        {"id": "d", "sourcePreference": "Avoid bathroom cleaning", "text": "Rotate chores fairly"},
    ])
    assert [row["id"] for row in result] == ["a", "c", "d"]


def test_constraint_repository_deduplicates_replayed_index_entries() -> None:
    """Repeated imports must not make one derived preference appear multiple times."""
    from accord_api.models import DerivedConstraint, PrivacyClassification

    context = build_context(persistence=False)
    constraint = DerivedConstraint(
        constraint_id="constraint-unique-1",
        household_id="house-unique",
        member_id="member-unique",
        category="task_preference",
        preference_or_requirement="Prefers cooking",
        importance_weight=0.8,
        flexibility=0.4,
        privacy_classification=PrivacyClassification.SHAREABLE_DERIVED,
        source_session_reference="session-unique",
    )
    context.constraints.create_many([constraint, constraint])

    assert [row.constraint_id for row in context.constraints.list_by_member("member-unique")] == ["constraint-unique-1"]
    assert [row.constraint_id for row in context.constraints.list_shareable_by_household("house-unique")] == ["constraint-unique-1"]


def test_demo_reset_is_idempotent_and_seeds_four_expenses_with_subset_split() -> None:
    get_context().reset()
    client = TestClient(create_app())
    first = client.post("/api/demo/roommates/reset")
    assert first.status_code == 201, first.text
    first_assignments = first.json()["assignments"]
    household_id = first.json()["household"]["householdId"]
    first_task_names = [" ".join(row["task"].casefold().split()) for row in first_assignments]
    first_tasks = [row["assignmentId"] for row in first_assignments]
    first_expenses = client.get(f"/api/expenses/households/{household_id}", headers={"X-Member-Id": first.json()["members"][0]["memberId"]}).json()["expenses"]
    assert len(first_task_names) == len(set(first_task_names)), "demo reset should not seed duplicate chore names"

    second = client.post("/api/demo/roommates/reset")
    assert second.status_code == 201, second.text
    second_assignments = second.json()["assignments"]
    second_task_names = [" ".join(row["task"].casefold().split()) for row in second_assignments]
    second_tasks = [row["assignmentId"] for row in second_assignments]
    second_expenses = client.get(f"/api/expenses/households/{household_id}", headers={"X-Member-Id": second.json()["members"][0]["memberId"]}).json()["expenses"]
    assert len(first_tasks) == len(set(first_tasks))
    assert len(second_tasks) == len(set(second_tasks))
    assert len(second_task_names) == len(set(second_task_names)), "a repeated reset must not duplicate chores by name"
    assert len(second_tasks) == len(first_tasks)
    assert len(first_expenses) == len(second_expenses) == 4
    subset_expense = next(row for row in second_expenses if "two" in row["description"].lower())
    assert len(subset_expense["splitMemberIds"]) == 2


def test_mediation_session_votes_can_change_and_non_member_is_rejected() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    created = client.post("/api/mediation/sessions", headers={"X-Member-Id": member_ids[0]}, json=make_session_payload(household_id, member_ids))
    assert created.status_code == 201, created.text
    session_id = created.json()["session"]["sessionId"]

    # A different household's member cannot read or vote in this session.
    other_house = client.post("/api/households", json={"name": "Other"}).json()["household"]["householdId"]
    outsider = client.post(f"/api/households/{other_house}/members", json={"displayName": "Outsider", "role": "roommate"}).json()["member"]["memberId"]
    rejected = client.post(f"/api/mediation/sessions/{session_id}/vote", headers={"X-Member-Id": outsider}, json={"optionId": "option-1"})
    assert rejected.status_code == 404

    first = client.post(f"/api/mediation/sessions/{session_id}/vote", headers={"X-Member-Id": member_ids[0]}, json={"optionId": "option-1"})
    assert first.status_code == 200 and first.json()["voteChanged"] is False
    changed = client.post(f"/api/mediation/sessions/{session_id}/vote", headers={"X-Member-Id": member_ids[0]}, json={"optionId": "option-2"})
    assert changed.status_code == 200 and changed.json()["voteChanged"] is True
    assert changed.json()["session"]["voteCounts"]["option-2"] == 1
    waiting = client.post(f"/api/mediation/sessions/{session_id}/close", headers={"X-Member-Id": member_ids[0]})
    assert waiting.status_code == 409


def test_mediation_close_tie_rule_and_draft_agreement() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    response = client.post("/api/mediation/sessions", headers={"X-Member-Id": member_ids[0]}, json=make_session_payload(household_id, member_ids))
    session_id = response.json()["session"]["sessionId"]
    for index, member_id in enumerate(member_ids):
        option_id = f"option-{index + 1}"
        vote = client.post(f"/api/mediation/sessions/{session_id}/vote", headers={"X-Member-Id": member_id}, json={"optionId": option_id})
        assert vote.status_code == 200, vote.text
    closed = client.post(f"/api/mediation/sessions/{session_id}/close", headers={"X-Member-Id": member_ids[0]})
    assert closed.status_code == 200, closed.text
    assert closed.json()["session"]["tie"] is True
    assert closed.json()["session"]["winningOptionId"] == "option-1"
    assert "earliest option" in closed.json()["session"]["tieBreakRule"]
    assert closed.json()["agreement"]["status"] == "draft"
    assert "must submit it through" in closed.json()["agreement"]["rationale"]


def test_mediation_session_never_persists_raw_statement_text() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    response = client.post("/api/mediation/sessions", headers={"X-Member-Id": member_ids[0]}, json=make_session_payload(household_id, member_ids))
    assert response.status_code == 201
    session_id = response.json()["session"]["sessionId"]
    private_phrase = "my private medical situation is not for the household"
    serialized = json.dumps(get_context().mediation_sessions[session_id].__dict__ if hasattr(get_context().mediation_sessions[session_id], "__dict__") else {
        "topic": get_context().mediation_sessions[session_id].topic,
        "restatements": get_context().mediation_sessions[session_id].restatements,
        "options": get_context().mediation_sessions[session_id].options,
        "votes": get_context().mediation_sessions[session_id].votes,
    })
    assert private_phrase not in serialized
    assert response.json()["session"]["storedRawPrivateStatements"] is False


def test_fairness_eight_week_simulation_is_seeded_read_only() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    payload = {"householdId": household_id, "seed": 42, "preferenceWeight": 0.55}
    headers = {"X-Member-Id": member_ids[0]}
    first = client.post("/api/fairness/simulate-weeks", headers=headers, json=payload)
    second = client.post("/api/fairness/simulate-weeks", headers=headers, json=payload)
    assert first.status_code == 200, first.text
    assert second.status_code == 200, second.text
    a, b = first.json(), second.json()
    assert a["weeksSimulated"] == 8 and len(a["weeks"]) == 8
    assert a["accordCumulativeWorkloads"] == b["accordCumulativeWorkloads"]
    assert a["roundRobinCumulativeWorkloads"] == b["roundRobinCumulativeWorkloads"]
    assert a["weeks"] == b["weeks"]
    assert a["synthetic"] is True and "heuristic" in a["note"].lower()
    assert len(client.get(f"/api/assignments/households/{household_id}", headers=headers).json()["assignments"]) == 0


def test_expense_subset_custom_ratios_and_remainder_balance_to_zero() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    now = datetime.now(UTC).isoformat()
    r = client.post("/api/expenses", headers={"X-Member-Id": member_ids[0]}, json={
        "householdId": household_id, "payerMemberId": member_ids[0], "description": "Shared taxi", "amount": 0.05,
        "category": "transport", "expenseDate": now, "splitMemberIds": member_ids, "splitRatios": {member_ids[0]: 2, member_ids[1]: 1, member_ids[2]: 1},
    })
    assert r.status_code == 201, r.text
    r2 = client.post("/api/expenses", headers={"X-Member-Id": member_ids[0]}, json={
        "householdId": household_id, "payerMemberId": member_ids[1], "description": "Coffee for two", "amount": 0.01,
        "category": "food", "expenseDate": now, "splitMemberIds": [member_ids[0], member_ids[1]],
    })
    assert r2.status_code == 201, r2.text
    settle = client.get(f"/api/expenses/households/{household_id}/settle-up", headers={"X-Member-Id": member_ids[0]})
    assert settle.status_code == 200
    body = settle.json()
    assert body["netBalanceCents"] == 0
    assert sum(row["netBalance"] for row in body["balances"]) == pytest.approx(0)
    first_split = next(row for row in body["expenseSplits"] if row["description"] == "Shared taxi")["shares"]
    assert sum(row["amountCents"] for row in first_split) == 5
    split_by_member = {row["memberId"]: row["amountCents"] for row in first_split}
    assert split_by_member[member_ids[0]] == 3
    assert split_by_member[member_ids[1]] == split_by_member[member_ids[2]] == 1
    assert "largest fractional remainder" in body["note"]
    assert "No payment" in body["note"]


def test_privacy_dashboard_reflects_provider_configuration(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    client = TestClient(create_app())
    body = client.get("/api/privacy/dashboard").json()
    assert body["llmMode"] == "deterministic"
    assert body["providerConfigured"] is False
    assert any("raw private interview answers" in text.lower() for text in body["cannotSee"])
    monkeypatch.setenv("ACCORD_LLM_API_KEY", "test-only-placeholder")
    monkeypatch.setenv("ACCORD_LLM_BASE_URL", "https://example.invalid/v1")
    body2 = client.get("/api/privacy/dashboard").json()
    assert body2["llmMode"] == "provider"
    assert body2["providerConfigured"] is True
    assert "test-only-placeholder" not in json.dumps(body2)


def test_meal_plan_is_seven_day_draft_and_uses_shareable_data_only() -> None:
    get_context().reset()
    client = TestClient(create_app())
    household_id, member_ids = seed_household(client)
    response = client.post("/api/assistant/meal-plan", headers={"X-Member-Id": member_ids[0]}, json={"householdId": household_id})
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["schedule"]) == 7
    assert body["status"] == "draft" and body["saved"] is False
    assert body["requiresHouseholdConfirmation"] is True
    assert body["shareableDataOnly"] is True
    assert "private answers were read" in body["note"].lower()


def test_rate_limit_returns_429_with_helpful_error(monkeypatch) -> None:
    monkeypatch.delenv("ACCORD_LLM_API_KEY", raising=False)
    monkeypatch.setenv("ACCORD_ASSISTANT_RATE_LIMIT_PER_MIN", "1")
    client = TestClient(create_app())
    with _RATE_LOCK:
        _RATE_HITS.clear()
    assert client.post("/api/assistant/chat", json={"message": "hello"}).status_code == 200
    limited = client.post("/api/assistant/chat", json={"message": "hello again"})
    assert limited.status_code == 429
    assert limited.json()["error"]["code"] == "assistant_rate_limited"
    with _RATE_LOCK:
        _RATE_HITS.clear()


def test_reassign_assignment_requires_household_member_and_updates_index() -> None:
    get_context().reset()
    client = TestClient(create_app())
    reset = client.post("/api/demo/roommates/reset").json()
    household_id = reset["household"]["householdId"]
    members = reset["members"]
    assignments = reset["assignments"]
    assignment_id = assignments[0]["assignmentId"]
    response = client.post(f"/api/assignments/{assignment_id}/reassign", headers={"X-Member-Id": members[0]["memberId"]}, json={"memberId": members[1]["memberId"]})
    assert response.status_code == 200, response.text
    assert response.json()["assignment"]["memberId"] == members[1]["memberId"]
    assert assignment_id in [row["assignmentId"] for row in client.get(f"/api/assignments/households/{household_id}", headers={"X-Member-Id": members[0]["memberId"]}).json()["assignments"]]
    bad = client.post(f"/api/assignments/{assignment_id}/reassign", headers={"X-Member-Id": members[0]["memberId"]}, json={"memberId": "not-a-household-member"})
    assert bad.status_code == 404


def test_workload_drift_alert_is_on_demand_and_not_notified(monkeypatch) -> None:
    get_context().reset()
    client = TestClient(create_app())
    reset = client.post("/api/demo/roommates/reset").json()
    household_id = reset["household"]["householdId"]
    member_id = reset["members"][0]["memberId"]
    drift = client.get(f"/api/monitoring/workload-drift/{household_id}", headers={"X-Member-Id": member_id})
    assert drift.status_code == 200
    body = drift.json()
    assert body["windowDays"] == 21
    assert "No notification was sent" in body["note"]


def test_end_to_end_demo_to_mediation_vote_and_settle_up() -> None:
    get_context().reset()
    client = TestClient(create_app())
    reset = client.post("/api/demo/roommates/reset")
    assert reset.status_code == 201
    body = reset.json()
    household_id = body["household"]["householdId"]
    members = body["members"]
    member_ids = [m["memberId"] for m in members]
    headers = {"X-Member-Id": member_ids[0]}

    # Exercise the consented private interview workflow before the joint flow.
    interview = client.post("/api/interviews", json={"householdId": household_id, "memberId": member_ids[0]})
    assert interview.status_code == 201, interview.text
    interview_id = interview.json()["session"]["sessionId"]
    submitted = client.post(f"/api/interviews/{interview_id}/submit", headers=headers, json={
        "transcriptReference": f"local-demo://{household_id}/{member_ids[0]}/{interview_id}",
        "answers": {"availability": "Usually free after 6 PM", "chores": "Prefer cooking, avoid late laundry", "expenses": "Split groceries equally", "preferences": "Keep personal notes private"},
    })
    assert submitted.status_code == 200, submitted.text
    assert client.get(f"/api/interviews/{interview_id}/private", headers=headers).status_code == 200
    assert client.post(f"/api/interviews/{interview_id}/complete", headers=headers).status_code == 200
    derived = client.post(f"/api/constraints/derive/{interview_id}", headers=headers)
    assert derived.status_code == 200, derived.text
    shared = client.get(f"/api/constraints/households/{household_id}/shared", headers=headers)
    assert shared.status_code == 200
    assert all(row.get("privacyClassification") == "shareable_derived" for row in shared.json()["constraints"])
    assert all("Keep personal notes private" not in json.dumps(row) for row in shared.json()["constraints"])

    fairness = client.post("/api/fairness/compare", headers=headers, json={"householdId": household_id})
    assert fairness.status_code == 200 and fairness.json()["note"]
    weekly_sim = client.post("/api/fairness/simulate-weeks", headers=headers, json={"householdId": household_id, "seed": 19})
    assert weekly_sim.status_code == 200 and len(weekly_sim.json()["weeks"]) == 8
    session_response = client.post("/api/mediation/sessions", headers=headers, json=make_session_payload(household_id, member_ids))
    assert session_response.status_code == 201
    session_id = session_response.json()["session"]["sessionId"]
    for index, member_id in enumerate(member_ids):
        vote = client.post(f"/api/mediation/sessions/{session_id}/vote", headers={"X-Member-Id": member_id}, json={"optionId": f"option-{(index % 2) + 1}"})
        assert vote.status_code == 200
    closed = client.post(f"/api/mediation/sessions/{session_id}/close", headers=headers)
    assert closed.status_code == 200
    assert closed.json()["agreement"]["status"] == "draft"
    household = client.get(f"/api/households/{household_id}")
    assert household.status_code == 200
    settle = client.get(f"/api/expenses/households/{household_id}/settle-up", headers=headers)
    assert settle.status_code == 200
    assert settle.json()["netBalanceCents"] == 0


def test_sqlite_persists_safe_mediation_session_across_context_restart(tmp_path) -> None:
    from accord_api.models import MediationSession
    from datetime import UTC, datetime

    db = tmp_path / "mediation-persist.sqlite3"
    first = build_context(persistence=True, database_path=db)
    session = MediationSession(
        session_id="mediation-persist-1", household_id="house-1", topic="Fair chore rotation",
        restatements=[{"memberId": "m1", "label": "Member 1", "needsRestatement": "Needs predictable chores", "privateDetailsOmitted": True}],
        options=[{"id": "option-1", "title": "Rotate weekly", "proposal": "Rotate kitchen duty weekly", "tradeOff": "Less choice of day", "requiresHouseholdConfirmation": True}],
        created_at=datetime.now(UTC),
    )
    first.mediation_sessions[session.session_id] = session
    first.persist()
    restored = build_context(persistence=True, database_path=db)
    saved = restored.mediation_sessions[session.session_id]
    assert saved.topic == "Fair chore rotation"
    assert saved.options[0]["id"] == "option-1"
    assert all("statement" not in row for row in saved.restatements)


def test_workload_drift_uses_completion_time_for_recently_completed_older_task() -> None:
    """An old assignment completed today belongs in the current three-week drift window."""
    from datetime import timedelta

    get_context().reset()
    client = TestClient(create_app())
    reset = client.post("/api/demo/roommates/reset").json()
    household_id = reset["household"]["householdId"]
    assignment_data = reset["assignments"][0]
    member_id = assignment_data["memberId"]
    assignment = get_context().assignments.get(assignment_data["assignmentId"])
    assert assignment is not None
    assignment.assigned_date = datetime.now(UTC) - timedelta(days=90)
    get_context().assignments.update(assignment)

    completed = client.patch(
        f"/api/assignments/{assignment.assignment_id}/status",
        headers={"X-Member-Id": member_id},
        json={"status": "completed"},
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["assignment"]["completedAt"] is not None

    drift = client.get(
        f"/api/monitoring/workload-drift/{household_id}",
        headers={"X-Member-Id": member_id},
    )
    assert drift.status_code == 200, drift.text
    body = drift.json()
    share = next(row for row in body["memberShares"] if row["memberId"] == member_id)
    assert share["completedMinutes"] >= assignment.estimated_effort
    assert body["totalCompletedMinutes"] >= assignment.estimated_effort
