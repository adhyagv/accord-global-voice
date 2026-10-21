"""Explainable deterministic workload-balancing for household proposals.

This is a transparent heuristic, not a claim of objective or universally correct
fairness. It only considers constraints passed into the solver; private interview
answers are not part of this interface.
"""

from __future__ import annotations

import math
import re
from datetime import timedelta

from ..models import Assignment, AssignmentStatus, DerivedConstraint, PrivacyClassification
from ..solver_interface import DeterministicFairnessSolver, SolverInput, SolverOutput
from ..utils import utcnow

_TASK_GROUPS: dict[str, tuple[str, ...]] = {
    "kitchen": ("cook", "cooking", "meal", "food", "kitchen", "dish", "dishes"),
    "bathroom": ("bathroom", "toilet", "shower"),
    "cleaning": ("clean", "cleaning", "vacuum", "mop", "dust", "floor"),
    "waste": ("trash", "garbage", "waste", "recycling", "bin"),
    "laundry": ("laundry", "clothes", "washing", "washer"),
    "outdoor": ("garden", "outdoor", "yard", "plants"),
}


def _task_groups(text: str) -> set[str]:
    normalized = re.sub(r"[_-]+", " ", text.casefold())
    return {
        group for group, terms in _TASK_GROUPS.items()
        if any(re.search(rf"\b{re.escape(term)}\b", normalized) for term in terms)
    }


def _constraint_preference_delta(member_id: str, task: str, effort: float, constraints: list[DerivedConstraint], preference_weight: float = 1.0) -> float:
    """Return a small soft cost for avoidances and a benefit for preferences."""
    task_groups = _task_groups(task)
    if not task_groups:
        return 0.0
    adjustment = 0.0
    preference_weight = max(0.0, min(1.0, float(preference_weight)))
    for constraint in constraints:
        if (
            constraint.privacy_classification != PrivacyClassification.SHAREABLE_DERIVED
            or constraint.member_id != member_id
            or constraint.category.casefold() not in {"task_preference", "task_preferences", "preference"}
        ):
            continue
        text = constraint.preference_or_requirement.casefold()
        importance = max(0.0, min(1.0, float(constraint.importance_weight)))
        inflexibility = 1.0 - max(0.0, min(1.0, float(constraint.flexibility)))
        for clause in re.split(r"[,;]|\bbut\b", text):
            groups = _task_groups(clause)
            if not task_groups.intersection(groups):
                continue
            impact = effort * importance * inflexibility * 0.35 * preference_weight
            if re.search(r"\b(avoid|avoids|dislike|dislikes|cannot|can't|must not|do not want|don't want)\b", clause):
                adjustment += impact
            elif re.search(r"\b(prefer|prefers|like|likes|enjoy|enjoys)\b", clause):
                adjustment -= impact
    return adjustment


def _rotation_penalty(member_id: str, task: str, effort: float, constraints: list[DerivedConstraint], existing: list[Assignment], horizon_days: int) -> float:
    task_groups = _task_groups(task)
    penalty = 0.0
    for constraint in constraints:
        if (
            constraint.privacy_classification != PrivacyClassification.SHAREABLE_DERIVED
            or constraint.member_id != member_id
            or constraint.category.casefold() != "rotation"
        ):
            continue
        text = constraint.preference_or_requirement.casefold()
        if not re.search(r"avoid repeated|repeat|rotation|consecutive week", text):
            continue
        for prior in existing:
            if prior.member_id != member_id:
                continue
            prior_groups = _task_groups(prior.task)
            same_task = prior.task.casefold().replace("_", " ").strip() == task.casefold().replace("_", " ").strip()
            if same_task or (task_groups and task_groups.intersection(prior_groups)):
                impact = effort * max(0.0, min(1.0, constraint.importance_weight)) * (1 - max(0.0, min(1.0, constraint.flexibility))) * 0.45
                penalty = max(penalty, impact)
                break
    return penalty


def _suggest_date(member_id: str, base_date, index: int, constraints: list[DerivedConstraint], horizon_days: int):
    suggested = base_date + timedelta(days=index)
    availability = " ".join(
        constraint.preference_or_requirement.casefold()
        for constraint in constraints
        if constraint.privacy_classification == PrivacyClassification.SHAREABLE_DERIVED
        and constraint.member_id == member_id and constraint.category.casefold() == "availability"
    )
    if "weekend" in availability and ("prefer" in availability or "limited weekday" in availability):
        # Keep preference soft, but put the proposed task in a weekend block.
        days_to_saturday = (5 - suggested.weekday()) % 7
        suggested += timedelta(days=days_to_saturday)
    elif "weekday" in availability and "limited weekday" not in availability and suggested.weekday() >= 5:
        suggested += timedelta(days=(7 - suggested.weekday()))
    return suggested


class DeterministicWorkloadFairnessSolver(DeterministicFairnessSolver):
    """Balance effort while respecting explicit shareable preferences softly.

    Tasks are considered largest-first. Each task goes to the member with the
    lowest projected load plus a bounded preference/rotation adjustment; ties
    are broken by stable member ID. Existing assignments count as workload.
    """

    def generate_plan(self, solver_input: SolverInput) -> SolverOutput:
        member_ids = sorted(set(solver_input.member_ids))
        tasks = [
            task for task in solver_input.task_efforts
            if task.task.strip() and math.isfinite(float(task.estimated_effort)) and task.estimated_effort >= 0
        ]
        if not member_ids or not tasks:
            return SolverOutput(
                proposed_assignments=[],
                fairness_score=0.0,
                rationale="A plan needs at least one member and one valid task. No assignments were created.",
                tie_break_trace=["empty_or_invalid_inputs", f"valid_members:{len(member_ids)}", f"valid_tasks:{len(tasks)}"],
            )

        projected_load: dict[str, float] = {member_id: 0.0 for member_id in member_ids}
        historical_load: dict[str, float] = {member_id: 0.0 for member_id in member_ids}
        for assignment in solver_input.existing_assignments:
            if assignment.member_id not in projected_load:
                continue
            effort = float(assignment.estimated_effort)
            if not math.isfinite(effort) or effort <= 0:
                continue
            weight = 0.35 if assignment.status == AssignmentStatus.COMPLETED else 1.0
            try:
                age_days = (utcnow() - assignment.assigned_date).total_seconds() / 86400
            except (TypeError, ValueError):
                age_days = 0.0
            if age_days > 0:
                weight *= max(0.25, 1.0 - (age_days / max(solver_input.horizon_days, 1)))
            contribution = effort * weight
            projected_load[assignment.member_id] += contribution
            historical_load[assignment.member_id] += contribution

        member_counts = {member_id: 0 for member_id in member_ids}
        task_order = sorted(tasks, key=lambda task: (-float(task.estimated_effort), task.task.strip().casefold()))
        assignments: list[Assignment] = []
        now = utcnow()
        allocation_trace: list[str] = []

        for index, task in enumerate(task_order):
            effort = float(task.estimated_effort)
            candidate_costs = {
                member_id: projected_load[member_id]
                + _constraint_preference_delta(member_id, task.task, effort, solver_input.constraints, solver_input.preference_weight)
                + _rotation_penalty(member_id, task.task, effort, solver_input.constraints, solver_input.existing_assignments, solver_input.horizon_days)
                for member_id in member_ids
            }
            recipient = min(member_ids, key=lambda member_id: (candidate_costs[member_id], member_counts[member_id], member_id))
            suggested_date = _suggest_date(recipient, now, index, solver_input.constraints, solver_input.horizon_days)
            assignments.append(
                Assignment(
                    assignment_id=f"proposal-{index + 1}",
                    member_id=recipient,
                    task=task.task.strip(),
                    frequency="weekly",
                    estimated_effort=effort,
                    assigned_date=suggested_date,
                    status=AssignmentStatus.SCHEDULED,
                )
            )
            projected_load[recipient] += effort
            member_counts[recipient] += 1
            allocation_trace.append(f"{task.task.strip()}:{effort:g}min->{recipient} (adjusted_cost={candidate_costs[recipient]:.1f})")

        minimum = min(projected_load.values())
        maximum = max(projected_load.values())
        total_proposed_effort = sum(float(task.estimated_effort) for task in task_order)
        spread = maximum - minimum
        denominator = max(sum(projected_load.values()), total_proposed_effort, 1.0)
        score = round(max(0.0, min(1.0, 1.0 - spread / denominator)), 2)
        member_loads = ", ".join(f"{member_id} {projected_load[member_id]:g} min" for member_id in member_ids)
        rationale = (
            f"Assigned {total_proposed_effort:g} minutes across {len(assignments)} proposed tasks. "
            f"Projected workload after this proposal: {member_loads} (spread {spread:g} min). "
            "Tasks were allocated largest-first to the lowest projected workload, with small adjustments for "
            "permitted task preferences, availability and rotation constraints; completed work is discounted for rotation. "
            "The score is a deterministic workload-balance heuristic, not a guarantee of objective fairness. "
            "Members should review the trade-offs and agree voluntarily."
        )
        return SolverOutput(
            proposed_assignments=assignments,
            fairness_score=score,
            rationale=rationale,
            tie_break_trace=[
                "member_order:stable_id",
                "task_order:effort_descending_then_name",
                "allocation:least_projected_workload_plus_soft_constraints",
                "completed_assignment_weight:0.35",
                f"shareable_constraints_available:{sum(c.privacy_classification == PrivacyClassification.SHAREABLE_DERIVED for c in solver_input.constraints)}",
                f"historical_loads:{historical_load}",
                f"allocations:{allocation_trace}",
                f"workload_spread_minutes:{spread:g}",
                f"heuristic_fairness_score:{score:.2f}",
                f"privacy_filter:{PrivacyClassification.SHAREABLE_DERIVED.value}_only",
            ],
        )


# Keep the historical class name as an alias so existing imports remain valid.
PlaceholderDeterministicFairnessSolver = DeterministicWorkloadFairnessSolver
