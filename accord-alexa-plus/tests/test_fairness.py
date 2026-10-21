from __future__ import annotations

import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from accord_api.models import Assignment, AssignmentStatus
from accord_api.services.fairness import DeterministicWorkloadFairnessSolver
from accord_api.solver_interface import SolverInput, TaskEffort


def make_input(member_ids: list[str], efforts: list[tuple[str, float]], existing: list[Assignment] | None = None) -> SolverInput:
    return SolverInput(
        household_id="h1",
        member_ids=member_ids,
        constraints=[],
        task_efforts=[TaskEffort(task=name, estimated_effort=effort) for name, effort in efforts],
        availability={},
        flexibility={},
        weights={},
        existing_assignments=existing or [],
        horizon_days=14,
    )


def test_large_tasks_are_distributed_by_projected_workload() -> None:
    solver = DeterministicWorkloadFairnessSolver()
    result = solver.generate_plan(make_input(["m1", "m2"], [("dishes", 10), ("bathroom", 40), ("trash", 30), ("floors", 20)]))

    loads = {"m1": 0.0, "m2": 0.0}
    for assignment in result.proposed_assignments:
        loads[assignment.member_id] += assignment.estimated_effort
    assert abs(loads["m1"] - loads["m2"]) <= 10
    assert result.fairness_score > 0.8
    assert "workload-balance heuristic" in result.rationale


def test_existing_workload_influences_next_assignment() -> None:
    existing = [
        Assignment("a1", "m1", "previous clean", "weekly", 90, datetime.now(UTC), AssignmentStatus.SCHEDULED)
    ]
    solver = DeterministicWorkloadFairnessSolver()
    result = solver.generate_plan(make_input(["m1", "m2"], [("dishes", 20)], existing))
    assert result.proposed_assignments[0].member_id == "m2"


def test_solver_is_deterministic_and_deduplicates_member_ids() -> None:
    solver = DeterministicWorkloadFairnessSolver()
    solver_input = make_input(["m2", "m1", "m1"], [("Trash", 20), ("Dishes", 20), ("Bathroom", 40)])
    first = solver.generate_plan(solver_input)
    second = solver.generate_plan(solver_input)
    assert [(item.task, item.member_id) for item in first.proposed_assignments] == [(item.task, item.member_id) for item in second.proposed_assignments]
    assert all(item.member_id in {"m1", "m2"} for item in first.proposed_assignments)


def test_empty_or_invalid_input_returns_explained_empty_proposal() -> None:
    solver = DeterministicWorkloadFairnessSolver()
    result = solver.generate_plan(make_input([], [("", 12), ("Bad", float("nan"))]))
    assert result.proposed_assignments == []
    assert result.fairness_score == 0.0
    assert "valid_tasks:0" in result.tie_break_trace


def test_explicit_shareable_task_preference_is_considered_softly() -> None:
    from accord_api.models import DerivedConstraint, PrivacyClassification

    constraint = DerivedConstraint(
        constraint_id="c1",
        household_id="h1",
        member_id="m1",
        category="task_preference",
        preference_or_requirement="prefers cooking-related tasks, avoid bathroom cleaning",
        importance_weight=0.9,
        flexibility=0.1,
        privacy_classification=PrivacyClassification.SHAREABLE_DERIVED,
        source_session_reference="s1",
    )
    solver = DeterministicWorkloadFairnessSolver()
    solver_input = make_input(["m1", "m2"], [("bathroom cleaning", 30), ("meal prep", 30)])
    solver_input.constraints = [constraint]
    result = solver.generate_plan(solver_input)
    allocation = {item.task: item.member_id for item in result.proposed_assignments}
    assert allocation["bathroom cleaning"] == "m2"
    assert allocation["meal prep"] == "m1"
    assert "task preferences" in result.rationale


def test_weekend_availability_places_preferred_task_on_weekend() -> None:
    from accord_api.models import DerivedConstraint, PrivacyClassification

    constraint = DerivedConstraint(
        constraint_id="c2",
        household_id="h1",
        member_id="m1",
        category="availability",
        preference_or_requirement="limited weekday availability, prefer weekend blocks",
        importance_weight=0.8,
        flexibility=0.2,
        privacy_classification=PrivacyClassification.SHAREABLE_DERIVED,
        source_session_reference="s2",
    )
    solver_input = make_input(["m1"], [("laundry", 25)])
    solver_input.constraints = [constraint]
    result = DeterministicWorkloadFairnessSolver().generate_plan(solver_input)
    assert result.proposed_assignments[0].assigned_date.weekday() in (5, 6)


def test_private_constraints_do_not_influence_shared_fairness_proposal() -> None:
    from accord_api.models import DerivedConstraint, PrivacyClassification

    private_constraint = DerivedConstraint(
        constraint_id="private-c1",
        household_id="h1",
        member_id="m1",
        category="task_preference",
        preference_or_requirement="strongly prefers cooking, must avoid bathroom cleaning",
        importance_weight=1.0,
        flexibility=0.0,
        privacy_classification=PrivacyClassification.PRIVATE,
        source_session_reference="private-session",
    )
    plain_input = make_input(["m1", "m2"], [("bathroom cleaning", 30), ("meal prep", 30)])
    private_input = make_input(["m1", "m2"], [("bathroom cleaning", 30), ("meal prep", 30)])
    private_input.constraints = [private_constraint]

    solver = DeterministicWorkloadFairnessSolver()
    plain = solver.generate_plan(plain_input)
    with_private = solver.generate_plan(private_input)

    assert [(item.task, item.member_id) for item in with_private.proposed_assignments] == [
        (item.task, item.member_id) for item in plain.proposed_assignments
    ]
    assert "shareable_constraints_available:0" in with_private.tie_break_trace


def test_private_availability_does_not_change_proposed_date() -> None:
    from datetime import datetime
    from accord_api.models import DerivedConstraint, PrivacyClassification
    from accord_api.services.fairness import _suggest_date

    constraint = DerivedConstraint(
        constraint_id="private-availability",
        household_id="h1",
        member_id="m1",
        category="availability",
        preference_or_requirement="limited weekday availability, prefer weekend blocks",
        importance_weight=1.0,
        flexibility=0.0,
        privacy_classification=PrivacyClassification.PRIVATE,
        source_session_reference="private-session",
    )
    base_date = datetime(2026, 10, 15)  # Thursday
    proposed = _suggest_date("m1", base_date, 0, [constraint], 14)
    assert proposed == base_date
