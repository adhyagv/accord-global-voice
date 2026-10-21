from __future__ import annotations

import sys
from datetime import datetime
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "packages" / "sim" / "src"))

from accord_sim.generator import DefaultSimulationProvider  # noqa: E402


class TestSimulationDataValidity(unittest.TestCase):
    def test_simulated_timeline_is_14_days_and_references_valid_entities(self) -> None:
        provider = DefaultSimulationProvider(seed=11)
        household = provider.synthetic_household("h1", "Maple House")
        members = provider.synthetic_members("h1", count=3)
        member_ids = [member["memberId"] for member in members]

        timeline = provider.simulate_14_day_timeline(
            household_id=household["householdId"],
            member_ids=member_ids,
            start_at=datetime(2026, 1, 1, 9, 0, 0),
        )

        self.assertEqual(timeline["durationDays"], 14)
        self.assertEqual(len(timeline["monitoringSignals"]), 14)

        assignment_ids = {a["assignmentId"] for a in timeline["assignments"]}
        timeline_member_ids = {a["memberId"] for a in timeline["assignments"]}

        for signal in timeline["monitoringSignals"]:
            self.assertIn(signal["assignmentReference"], assignment_ids)
            self.assertIn(signal["memberReference"], timeline_member_ids)
            self.assertGreaterEqual(signal["expectedContribution"], signal["observedContribution"])


if __name__ == "__main__":
    unittest.main()
