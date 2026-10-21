"""Interfaces for simulated Accord integrations and synthetic data flows."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol


class SimulationProvider(Protocol):
    def synthetic_household(self, household_id: str, name: str) -> dict: ...

    def synthetic_members(self, household_id: str, count: int = 3) -> list[dict]: ...

    def simulated_interview_responses(self, household_id: str, member_ids: list[str]) -> list[dict]: ...

    def simulated_assignments(self, household_id: str, member_ids: list[str], start_at: datetime) -> list[dict]: ...

    def simulated_monitoring_signals(self, assignments: list[dict], days: int = 14) -> list[dict]: ...

    def simulate_14_day_timeline(self, household_id: str, member_ids: list[str], start_at: datetime) -> dict: ...
