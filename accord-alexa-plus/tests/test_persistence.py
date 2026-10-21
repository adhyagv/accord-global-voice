from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))
sys.path.insert(0, str(ROOT / "packages" / "sim" / "src"))

from accord_api.models import ConsentStatus
from accord_api.services.context import build_context
from accord_api.services.use_cases import AccordService


def test_sqlite_round_trip_preserves_household_member_identity_and_private_session(tmp_path: Path) -> None:
    database = tmp_path / "accord.sqlite3"
    first_context = build_context(persistence=True, database_path=database)
    service = AccordService(first_context)

    household = service.create_household("Persistence Home", {"type": "family"})
    member = service.add_member(
        household.household_id, "Adhya", "owner", consent_status=ConsentStatus.GRANTED
    )
    session = service.start_interview(household.household_id, member.member_id)
    service.submit_interview(
        session.session_id, member.member_id, "local-demo-reference",
        {"availability": "weekday evenings", "preference": "likes cooking"},
    )
    service.complete_interview(session.session_id, member.member_id)
    first_context.persist()

    restored_context = build_context(persistence=True, database_path=database)
    restored_household = restored_context.households.get(household.household_id)
    restored_member = restored_context.members.get(member.member_id)
    restored_session = restored_context.interviews.get(session.session_id)

    assert restored_household is not None
    assert restored_member is not None
    assert restored_member.consent_status is ConsentStatus.GRANTED
    assert restored_household.members[0] is restored_member
    assert restored_session is not None
    assert restored_session.private_answers == {
        "availability": "weekday evenings",
        "preference": "likes cooking",
    }
    assert restored_session.status.value == "completed"


def test_sqlite_snapshot_does_not_corrupt_ids_after_restart(tmp_path: Path) -> None:
    database = tmp_path / "accord.sqlite3"
    context = build_context(persistence=True, database_path=database)
    service = AccordService(context)
    first = service.create_household("One", {})
    context.persist()

    restored = build_context(persistence=True, database_path=database)
    second = AccordService(restored).create_household("Two", {})

    assert first.household_id == "household-1"
    assert second.household_id == "household-2"


def test_fastapi_middleware_persists_api_changes_across_context_restart(tmp_path: Path, monkeypatch) -> None:
    import accord_api.dependencies as dependencies
    from fastapi.testclient import TestClient
    from accord_api.app import create_app

    database = tmp_path / "api-state.sqlite3"
    monkeypatch.setenv("ACCORD_PERSISTENCE", "sqlite")
    monkeypatch.setenv("ACCORD_DB_PATH", str(database))
    monkeypatch.setattr(dependencies, "_CTX", None)
    monkeypatch.setattr(dependencies, "_SERVICE", None)

    with TestClient(create_app()) as client:
        created = client.post("/api/households", json={"name": "Saved Home"})
        assert created.status_code == 201
        household_id = created.json()["household"]["householdId"]

    # Simulate a process restart by forcing lazy dependency creation again.
    dependencies._CTX = None
    dependencies._SERVICE = None
    with TestClient(create_app()) as restarted_client:
        loaded = restarted_client.get(f"/api/households/{household_id}")
        assert loaded.status_code == 200
        assert loaded.json()["household"]["name"] == "Saved Home"
        assert restarted_client.get("/healthz").json()["storage"] == "sqlite"
