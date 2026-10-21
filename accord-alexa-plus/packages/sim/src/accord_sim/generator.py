"""Deterministic synthetic data generation for Accord simulations."""

from __future__ import annotations

from datetime import datetime, timedelta
from random import Random

from .interfaces import SimulationProvider


class DefaultSimulationProvider(SimulationProvider):
    def __init__(self, seed: int = 7) -> None:
        self._rng = Random(seed)

    def synthetic_household(self, household_id: str, name: str) -> dict:
        return {
            "householdId": household_id,
            "name": name,
            "scenarioMetadata": {
                "mode": "simulated",
                "description": "Three roommates negotiating household chores",
                "scenario": "priya-rahul-aman",
            },
            "members": [],
        }

    def synthetic_members(self, household_id: str, count: int = 3) -> list[dict]:
        base = [
            {
                "displayName": "Priya",
                "role": "roommate",
                "consentStatus": "granted",
                "privacyStatus": "private_only",
                "profile": {"prefers": "cooking", "dislikes": "bathroom cleaning"},
            },
            {
                "displayName": "Rahul",
                "role": "roommate",
                "consentStatus": "granted",
                "privacyStatus": "private_only",
                "profile": {
                    "prefers": "cleaning",
                    "availability": "limited weekday availability",
                },
            },
            {
                "displayName": "Aman",
                "role": "roommate",
                "consentStatus": "granted",
                "privacyStatus": "private_only",
                "profile": {"schedule": "flexible", "dislikes": "repeated chores"},
            },
        ]
        result = []
        for idx in range(min(count, len(base))):
            payload = dict(base[idx])
            payload["memberId"] = f"{household_id}-member-{idx + 1}"
            result.append(payload)
        return result

    def simulated_interview_responses(self, household_id: str, member_ids: list[str]) -> list[dict]:
        interview_templates = [
            {
                "category": "task_preference",
                "preferenceOrRequirement": "prefers cooking-related tasks, avoid bathroom cleaning",
                "importanceWeight": 0.82,
                "flexibility": 0.30,
            },
            {
                "category": "availability",
                "preferenceOrRequirement": "limited weekday availability, prefer weekend blocks",
                "importanceWeight": 0.78,
                "flexibility": 0.45,
            },
            {
                "category": "rotation",
                "preferenceOrRequirement": "avoid repeated chores in consecutive weeks",
                "importanceWeight": 0.66,
                "flexibility": 0.70,
            },
        ]
        responses = []
        for idx, member_id in enumerate(member_ids):
            template = interview_templates[idx % len(interview_templates)]
            responses.append(
                {
                    "sessionId": f"{household_id}-session-{idx + 1}",
                    "householdId": household_id,
                    "memberId": member_id,
                    "status": "completed",
                    "transcriptReference": f"private://{household_id}/{member_id}/session-{idx + 1}",
                    "derivedConstraints": [
                        {
                            "constraintId": f"{member_id}-c1",
                            "memberId": member_id,
                            "category": template["category"],
                            "preferenceOrRequirement": template["preferenceOrRequirement"],
                            "importanceWeight": template["importanceWeight"],
                            "flexibility": template["flexibility"],
                            "privacyClassification": "shareable_derived",
                            "sourceSessionReference": f"{household_id}-session-{idx + 1}",
                        }
                    ],
                }
            )
        return responses

    def simulated_assignments(self, household_id: str, member_ids: list[str], start_at: datetime) -> list[dict]:
        tasks = ["meal_prep", "bathroom_cleaning", "trash_and_recycling"]
        effort = [35.0, 40.0, 20.0]
        assignments = []
        for idx, member_id in enumerate(member_ids):
            assignments.append(
                {
                    "assignmentId": f"{household_id}-a-{idx + 1}",
                    "memberId": member_id,
                    "task": tasks[idx % len(tasks)],
                    "frequency": "weekly",
                    "estimatedEffort": effort[idx % len(effort)],
                    "assignedDate": (start_at + timedelta(days=idx)).isoformat(),
                    "status": "scheduled",
                }
            )
        return assignments

    def simulated_monitoring_signals(self, assignments: list[dict], days: int = 14) -> list[dict]:
        if not assignments:
            return []

        base_time = datetime.fromisoformat(assignments[0]["assignedDate"])
        signals = []
        for day in range(days):
            assignment = assignments[day % len(assignments)]
            expected = assignment["estimatedEffort"]
            deterministic_variance = self._rng.uniform(0.03, 0.22)
            observed = max(0.0, expected * (1.0 - deterministic_variance))
            signals.append(
                {
                    "signalId": f"signal-{day + 1}",
                    "assignmentReference": assignment["assignmentId"],
                    "memberReference": assignment["memberId"],
                    "expectedContribution": expected,
                    "observedContribution": round(observed, 2),
                    "timestamp": (base_time + timedelta(days=day)).isoformat(),
                }
            )
        return signals

    def simulate_14_day_timeline(self, household_id: str, member_ids: list[str], start_at: datetime) -> dict:
        assignments = self.simulated_assignments(household_id, member_ids, start_at)
        signals = self.simulated_monitoring_signals(assignments, days=14)
        return {
            "householdId": household_id,
            "durationDays": 14,
            "assignments": assignments,
            "monitoringSignals": signals,
            "simulatedIntegrations": {
                "voice": "simulated",
                "notifications": "simulated",
                "calendar": "simulated",
                "householdActivity": "simulated",
            },
        }
