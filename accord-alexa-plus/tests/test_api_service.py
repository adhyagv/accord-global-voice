from __future__ import annotations

import os
import sys
from pathlib import Path
import unittest

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
# Keep API integration tests isolated from a developer's local persistent demo DB.
os.environ["ACCORD_PERSISTENCE"] = "memory"
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from accord_api.app import create_app  # noqa: E402
from accord_api.dependencies import get_context  # noqa: E402


class TestAccordApiService(unittest.TestCase):
    def setUp(self) -> None:
        get_context().reset()
        self.client = TestClient(create_app())

    def _seed_household(self) -> tuple[str, list[str]]:
        household = self.client.post(
            "/api/households", json={"name": "Maple House", "scenarioMetadata": {"mode": "simulated"}}
        ).json()["household"]
        household_id = household["householdId"]

        member_ids: list[str] = []
        for name in ["Priya", "Rahul", "Aman"]:
            payload = {
                "displayName": name,
                "role": "roommate",
            }
            created = self.client.post(f"/api/households/{household_id}/members", json=payload).json()["member"]
            member_id = created["memberId"]
            consent = self.client.patch(
                f"/api/households/{household_id}/members/{member_id}/consent",
                headers={"X-Member-Id": member_id},
                json={"consentStatus": "granted"},
            )
            self.assertEqual(consent.status_code, 200)
            member_ids.append(member_id)
        return household_id, member_ids

    def test_household_creation_and_member_listing(self) -> None:
        household_id, member_ids = self._seed_household()
        self.assertEqual(len(member_ids), 3)

        fetched = self.client.get(f"/api/households/{household_id}")
        self.assertEqual(fetched.status_code, 200)

        members = self.client.get(f"/api/households/{household_id}/members").json()["members"]
        self.assertEqual([m["displayName"] for m in members], ["Priya", "Rahul", "Aman"])

    def test_interview_lifecycle_and_privacy_isolation(self) -> None:
        household_id, member_ids = self._seed_household()
        priya, rahul, _ = member_ids

        session = self.client.post(
            "/api/interviews", json={"householdId": household_id, "memberId": priya}
        ).json()["session"]

        submitted = self.client.post(
            f"/api/interviews/{session['sessionId']}/submit",
            headers={"X-Member-Id": priya},
            json={"transcriptReference": "private://household/priya/session-1"},
        )
        self.assertEqual(submitted.status_code, 200)

        completed = self.client.post(
            f"/api/interviews/{session['sessionId']}/complete",
            headers={"X-Member-Id": priya},
        )
        self.assertEqual(completed.status_code, 200)

        private_view = self.client.get(
            f"/api/interviews/{session['sessionId']}/private", headers={"X-Member-Id": priya}
        )
        self.assertIn("transcriptReference", private_view.json()["session"])

        unauthorized = self.client.get(
            f"/api/interviews/{session['sessionId']}/private", headers={"X-Member-Id": rahul}
        )
        self.assertEqual(unauthorized.status_code, 404)
        self.assertEqual(unauthorized.json()["error"]["code"], "resource_not_found")

    def test_constraints_agreements_assignments_monitoring_and_drift(self) -> None:
        household_id, member_ids = self._seed_household()
        priya, rahul, aman = member_ids

        derived_ids: list[str] = []
        for member_id in member_ids:
            session = self.client.post(
                "/api/interviews", json={"householdId": household_id, "memberId": member_id}
            ).json()["session"]
            self.client.post(
                f"/api/interviews/{session['sessionId']}/submit",
                headers={"X-Member-Id": member_id},
                json={"transcriptReference": f"private://{household_id}/{member_id}/session"},
            )
            self.client.post(
                f"/api/interviews/{session['sessionId']}/complete",
                headers={"X-Member-Id": member_id},
            )
            constraints = self.client.post(
                f"/api/constraints/derive/{session['sessionId']}",
                headers={"X-Member-Id": member_id},
            ).json()["constraints"]
            derived_ids.extend(
                [c["constraintId"] for c in constraints if c["privacyClassification"] == "shareable_derived"]
            )

        member_private_constraints = self.client.get(
            f"/api/constraints/members/{priya}", headers={"X-Member-Id": priya}
        )
        self.assertEqual(member_private_constraints.status_code, 200)

        unauthorized_constraints = self.client.get(
            f"/api/constraints/members/{priya}", headers={"X-Member-Id": rahul}
        )
        self.assertEqual(unauthorized_constraints.status_code, 404)

        shared_constraints = self.client.get(
            f"/api/constraints/households/{household_id}/shared", headers={"X-Member-Id": aman}
        ).json()["constraints"]
        self.assertTrue(all(c["privacyClassification"] == "shareable_derived" for c in shared_constraints))

        agreement = self.client.post(
            "/api/agreements/generate",
            headers={"X-Member-Id": priya},
            json={"householdId": household_id, "derivedConstraintIds": derived_ids},
        ).json()["agreement"]

        agreement_id = agreement["agreementId"]
        version = agreement["version"]

        self.client.post(
            f"/api/agreements/{agreement_id}/versions/{version}/approve",
            headers={"X-Member-Id": priya},
        )
        changed = self.client.post(
            f"/api/agreements/{agreement_id}/versions/{version}/counter",
            headers={"X-Member-Id": rahul},
            json={"memberId": rahul, "proposalDeltaSummary": "reduce weekday load"},
        ).json()["agreement"]
        self.assertEqual(changed["status"], "changes_requested")

        vetoed = self.client.post(
            f"/api/agreements/{agreement_id}/versions/{version}/veto",
            headers={"X-Member-Id": aman},
        ).json()["agreement"]
        self.assertEqual(vetoed["status"], "vetoed")

        second = self.client.post(
            "/api/agreements/generate",
            headers={"X-Member-Id": priya},
            json={"householdId": household_id, "derivedConstraintIds": derived_ids},
        ).json()["agreement"]

        for member_id in member_ids:
            self.client.post(
                f"/api/agreements/{second['agreementId']}/versions/{second['version']}/approve",
                headers={"X-Member-Id": member_id},
            )
        active = self.client.post(
            f"/api/agreements/{second['agreementId']}/versions/{second['version']}/activate",
            headers={"X-Member-Id": priya},
        ).json()["agreement"]
        self.assertEqual(active["status"], "active")

        assignments = self.client.get(
            f"/api/assignments/households/{household_id}", headers={"X-Member-Id": priya}
        ).json()["assignments"]
        self.assertGreater(len(assignments), 0)

        assignment = assignments[0]
        updated = self.client.patch(
            f"/api/assignments/{assignment['assignmentId']}/status",
            headers={"X-Member-Id": assignment['memberId']},
            json={"status": "completed"},
        )
        self.assertEqual(updated.status_code, 200)

        unauthorized_assignment_update = self.client.patch(
            f"/api/assignments/{assignment['assignmentId']}/status",
            headers={"X-Member-Id": priya if assignment['memberId'] != priya else rahul},
            json={"status": "missed"},
        )
        self.assertEqual(unauthorized_assignment_update.status_code, 404)

        signal = self.client.post(
            "/api/monitoring/signals",
            headers={"X-Member-Id": priya},
            json={
                "householdId": household_id,
                "assignmentReference": assignment["assignmentId"],
                "memberReference": assignment["memberId"],
                "expectedContribution": 30,
                "observedContribution": 20,
                "timestamp": "2026-01-02T10:00:00+00:00",
            },
        )
        self.assertEqual(signal.status_code, 201)

        drift = self.client.post(
            "/api/drift/generate",
            headers={"X-Member-Id": priya},
            json={"agreementId": second["agreementId"], "version": second["version"]},
        ).json()["driftReport"]
        self.assertIn("severity", drift)

        retrieved_drift = self.client.get(
            f"/api/drift/{drift['driftId']}", headers={"X-Member-Id": aman}
        )
        self.assertEqual(retrieved_drift.status_code, 200)

        renegotiation = self.client.post(
            "/api/drift/renegotiations/start",
            headers={"X-Member-Id": priya},
            json={"householdId": household_id, "driftId": drift["driftId"]},
        )
        self.assertEqual(renegotiation.status_code, 201)
        self.assertEqual(renegotiation.json()["renegotiation"]["status"], "interviewing")

    def test_demo_endpoint_is_deterministic_and_shared_safe(self) -> None:
        first = self.client.post("/api/demo/roommates/reset")
        second = self.client.post("/api/demo/roommates/reset")

        self.assertEqual(first.status_code, 201)
        self.assertEqual(second.status_code, 201)

        first_payload = first.json()
        second_payload = second.json()

        self.assertEqual(first_payload["mode"], "DEVELOPMENT/DEMO ONLY")
        self.assertEqual(
            [m["displayName"] for m in first_payload["members"]], ["Priya", "Rahul", "Aman"]
        )
        self.assertEqual(
            [a["task"] for a in first_payload["assignments"]],
            [a["task"] for a in second_payload["assignments"]],
        )
        self.assertNotIn("transcriptReference", str(first_payload))

    def test_openapi_and_health(self) -> None:
        health = self.client.get("/healthz")
        self.assertEqual(health.status_code, 200)

        openapi = self.client.get("/openapi.json")
        self.assertEqual(openapi.status_code, 200)
        self.assertIn("/api/demo/roommates/reset", openapi.json()["paths"])


if __name__ == "__main__":
    unittest.main()
