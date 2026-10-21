"""SQLite snapshot persistence for the local Accord prototype.

The domain services continue to use the repository interfaces and current in-memory
repository implementations. This store serializes their complete domain state to one
SQLite transaction after each API request and restores it when the application starts.
SQLite is included with Python, so local setup needs no database server or extra package.

This is a local-development persistence adapter, not a production multi-user database.
Private interview answers are stored on disk in the local database; use synthetic data
only unless encrypted storage and real authentication are configured.
"""

from __future__ import annotations

import json
import os
import sqlite3
import threading
from dataclasses import fields, is_dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any

from . import models


MODEL_TYPES: dict[str, type] = {
    name: getattr(models, name)
    for name in (
        "Member",
        "Household",
        "PrivateInterviewSession",
        "DerivedConstraint",
        "Assignment",
        "Expense",
        "Counteroffer",
        "AgreementVersion",
        "MonitoringSignal",
        "DriftReport",
        "RenegotiationCycle",
        "MediationSession",
    )
}
ENUM_TYPES: dict[str, type[Enum]] = {
    name: getattr(models, name)
    for name in (
        "ConsentStatus",
        "PrivacyStatus",
        "PrivacyClassification",
        "InterviewStatus",
        "AgreementStatus",
        "AssignmentStatus",
        "DriftSeverity",
        "DriftStatus",
        "RenegotiationStatus",
    )
}


def _encode(value: Any) -> Any:
    if isinstance(value, Enum):
        return {"__kind__": "enum", "type": type(value).__name__, "value": value.value}
    if isinstance(value, datetime):
        return {"__kind__": "datetime", "value": value.isoformat()}
    if is_dataclass(value) and not isinstance(value, type):
        return {
            "__kind__": "dataclass",
            "type": type(value).__name__,
            "fields": {field.name: _encode(getattr(value, field.name)) for field in fields(value)},
        }
    if isinstance(value, dict):
        return {str(key): _encode(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_encode(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    raise TypeError(f"Unsupported persistence value: {type(value).__name__}")


def _decode(value: Any) -> Any:
    if isinstance(value, list):
        return [_decode(item) for item in value]
    if not isinstance(value, dict):
        return value
    kind = value.get("__kind__")
    if kind == "datetime":
        return datetime.fromisoformat(value["value"])
    if kind == "enum":
        enum_type = ENUM_TYPES.get(value.get("type", ""))
        if enum_type is None:
            raise ValueError("Unknown enum type in Accord database")
        return enum_type(value["value"])
    if kind == "dataclass":
        model_type = MODEL_TYPES.get(value.get("type", ""))
        if model_type is None:
            raise ValueError("Unknown model type in Accord database")
        decoded_fields = {key: _decode(item) for key, item in value["fields"].items()}
        return model_type(**decoded_fields)
    return {key: _decode(item) for key, item in value.items()}


class SQLiteSnapshotStore:
    """Durably stores and restores all Accord repository state in SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self.database_path = str(database_path)
        self._lock = threading.RLock()
        if self.database_path != ":memory:":
            Path(self.database_path).expanduser().resolve().parent.mkdir(parents=True, exist_ok=True)
        self._initialize()

    @staticmethod
    def default_path() -> Path:
        configured = os.environ.get("ACCORD_DB_PATH")
        if configured:
            return Path(configured).expanduser()
        # persistence.py -> accord_api -> src -> api -> apps -> repository root
        root = Path(__file__).resolve().parents[4]
        return root / "data" / "accord.sqlite3"

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self.database_path, timeout=10)
        connection.execute("PRAGMA busy_timeout = 10000")
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    def _initialize(self) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("PRAGMA journal_mode = WAL")
            connection.execute(
                "CREATE TABLE IF NOT EXISTS accord_snapshot ("
                "id INTEGER PRIMARY KEY CHECK (id = 1), "
                "payload TEXT NOT NULL, "
                "updated_at TEXT NOT NULL)"
            )

    def load(self, context: Any) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT payload FROM accord_snapshot WHERE id = 1"
            ).fetchone()
        if row is None:
            return False
        payload = _decode(json.loads(row[0]))
        self._restore(context, payload)
        return True

    def save(self, context: Any) -> None:
        from datetime import UTC

        snapshot = self._snapshot(context)
        payload = json.dumps(_encode(snapshot), ensure_ascii=False, separators=(",", ":"))
        with self._lock, self._connect() as connection:
            connection.execute(
                "INSERT INTO accord_snapshot (id, payload, updated_at) VALUES (1, ?, ?) "
                "ON CONFLICT(id) DO UPDATE SET payload = excluded.payload, updated_at = excluded.updated_at",
                (payload, datetime.now(UTC).isoformat()),
            )
            connection.commit()

    @staticmethod
    def _snapshot(context: Any) -> dict[str, Any]:
        assignments = context.assignments
        return {
            "schema_version": 1,
            "households": list(context.households._items.values()),
            "members": {
                "items": list(context.members._items.values()),
                "by_household": dict(context.members._by_household),
            },
            "interviews": list(context.interviews._items.values()),
            "constraints": list(context.constraints._items.values()),
            "agreements": list(context.agreements._items.values()),
            "assignments": {
                "items": list(assignments._items.values()),
                "by_household": dict(assignments._household_index),
                "by_agreement": [
                    {"agreement_id": agreement_id, "version": version, "ids": ids}
                    for (agreement_id, version), ids in assignments._agreement_index.items()
                ],
            },
            "expenses": list(context.expenses._items.values()),
            "monitoring": {
                "items": list(context.monitoring._items.values()),
                "by_household": dict(context.monitoring._by_household),
            },
            "drift_reports": {
                "items": list(context.drift_reports._items.values()),
                "by_household": dict(context.drift_reports._by_household),
            },
            "renegotiations": {
                "items": list(context.renegotiations._items.values()),
                "by_household": dict(context.renegotiations._by_household),
            },
            "mediation_sessions": list(context.mediation_sessions.values()),
            "id_counters": dict(context.id_gen.prefix_counters),
        }

    @staticmethod
    def _restore(context: Any, payload: dict[str, Any]) -> None:
        # Clear repositories first. Household/member object identity is restored below
        # so consent updates stay in sync with the household membership list.
        context.reset()

        members_state = payload.get("members", {})
        member_by_id = {member.member_id: member for member in members_state.get("items", [])}
        household_state = payload.get("households", [])
        household_by_id = {household.household_id: household for household in household_state}
        for household in household_by_id.values():
            household.members = []
            context.households.create(household)

        for household_id, member_ids in members_state.get("by_household", {}).items():
            household = household_by_id.get(household_id)
            for member_id in member_ids:
                member = member_by_id.get(member_id)
                if member is None:
                    continue
                context.members.add(household_id, member)
                if household is not None:
                    household.add_member(member)

        # Restore any member records that were present but missing from an index.
        indexed_member_ids = {mid for ids in members_state.get("by_household", {}).values() for mid in ids}
        for member_id, member in member_by_id.items():
            if member_id not in indexed_member_ids:
                context.members._items[member_id] = member

        for session in payload.get("interviews", []):
            context.interviews.create(session)
        context.constraints.create_many(payload.get("constraints", []))

        assignment_state = payload.get("assignments", {})
        assignment_by_id = {
            assignment.assignment_id: assignment
            for assignment in assignment_state.get("items", [])
        }
        context.assignments.create_many(list(assignment_by_id.values()))
        for household_id, ids in assignment_state.get("by_household", {}).items():
            context.assignments.link_to_household(household_id, [aid for aid in ids if aid in assignment_by_id])
        for item in assignment_state.get("by_agreement", []):
            context.assignments.link_to_agreement(
                item["agreement_id"], int(item["version"]),
                [aid for aid in item["ids"] if aid in assignment_by_id],
            )

        for agreement in payload.get("agreements", []):
            # Share assignment instances between active agreement proposals and the
            # assignment repository, so status changes are reflected consistently.
            agreement.proposal = [
                assignment_by_id.get(item.assignment_id, item) for item in agreement.proposal
            ]
            context.agreements.create(agreement)
        for expense in payload.get("expenses", []):
            context.expenses.create(expense)

        monitoring_state = payload.get("monitoring", {})
        monitoring_by_id = {item.signal_id: item for item in monitoring_state.get("items", [])}
        for household_id, ids in monitoring_state.get("by_household", {}).items():
            for signal_id in ids:
                signal = monitoring_by_id.get(signal_id)
                if signal is not None:
                    context.monitoring.create(signal, household_id)

        drift_state = payload.get("drift_reports", {})
        drift_by_id = {item.drift_id: item for item in drift_state.get("items", [])}
        for household_id, ids in drift_state.get("by_household", {}).items():
            for drift_id in ids:
                report = drift_by_id.get(drift_id)
                if report is not None:
                    context.drift_reports.create(report, household_id)

        renegotiation_state = payload.get("renegotiations", {})
        renegotiation_by_id = {
            item.renegotiation_id: item for item in renegotiation_state.get("items", [])
        }
        for household_id, ids in renegotiation_state.get("by_household", {}).items():
            for renegotiation_id in ids:
                cycle = renegotiation_by_id.get(renegotiation_id)
                if cycle is not None:
                    context.renegotiations.create(cycle)

        context.mediation_sessions.update({
            item.session_id: item for item in payload.get("mediation_sessions", [])
        })
        context.id_gen.prefix_counters.update(payload.get("id_counters", {}))
