"""Deterministic fairness solver interface contract."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from .models import Assignment, DerivedConstraint


@dataclass(slots=True)
class TaskEffort:
    task: str
    estimated_effort: float


@dataclass(slots=True)
class SolverInput:
    household_id: str
    member_ids: list[str]
    constraints: list[DerivedConstraint]
    task_efforts: list[TaskEffort]
    availability: dict[str, str]
    flexibility: dict[str, float]
    weights: dict[str, float]
    existing_assignments: list[Assignment]
    horizon_days: int
    preference_weight: float = 1.0


@dataclass(slots=True)
class SolverOutput:
    proposed_assignments: list[Assignment]
    fairness_score: float
    rationale: str
    tie_break_trace: list[str]


class DeterministicFairnessSolver(Protocol):
    """Replaceable deterministic solver interface; no LLM decision-making."""

    def generate_plan(self, solver_input: SolverInput) -> SolverOutput: ...
