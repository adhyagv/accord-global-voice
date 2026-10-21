from __future__ import annotations
import re
from random import Random
from datetime import UTC, datetime

from fastapi import APIRouter, Depends

from ...dependencies import get_service
from ...privacy import caller_member_id
from ...services.structured_assistance import FAIRNESS_EXPLAINER_SYSTEM_PROMPT, optional_json_completion
from ...services.use_cases import AccordService
from ..schemas import FairnessCompareRequest, FairnessSimulationRequest
from ...models import Assignment, AssignmentStatus
from ...solver_interface import SolverInput, TaskEffort

router = APIRouter(prefix="/fairness", tags=["fairness & explainability"])


@router.post("/compare")
async def compare_fairness(
    payload: FairnessCompareRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Preview Accord's solver against a round-robin baseline; no writes occur."""
    tasks = [(task.task, task.estimatedEffort) for task in payload.tasks]
    result = service.compare_fairness(
        payload.householdId,
        requester_member_id,
        tasks,
        payload.preferenceWeight,
    )
    # Optional second pass: use the user's configured provider to paraphrase
    # the deterministic, privacy-safe allocation result. If malformed, ignore it.
    explanations = await optional_json_completion(
        FAIRNESS_EXPLAINER_SYSTEM_PROMPT,
        {
            "projectedWorkloads": result["solver"]["workloads"],
            "shareablePreferencesUsed": result["shareablePreferencesUsed"],
            "tasksAssigned": result["solver"]["assignments"],
        },
        max_tokens=600,
    )
    if explanations and isinstance(explanations.get("explanations"), list):
        expected_ids = {row["memberId"] for row in result["solver"]["workloads"]}
        candidates = {row.get("memberId"): row.get("explanation") for row in explanations["explanations"] if isinstance(row, dict)}
        if set(candidates) == expected_ids:
            valid = True
            for member_id, text in candidates.items():
                if not isinstance(text, str) or len(text) > 600 or len(re.findall(r"[.!?](?:\s|$)", text.strip())) != 2:
                    valid = False
                    break
            if valid:
                for row in result["solver"]["workloads"]:
                    row["explanation"] = candidates[row["memberId"]].strip()
                result["explanationMode"] = "llm"
    result.setdefault("explanationMode", "deterministic")
    return result


@router.post("/simulate-weeks")
def simulate_fairness_weeks(
    payload: FairnessSimulationRequest,
    requester_member_id: str = Depends(caller_member_id),
    service: AccordService = Depends(get_service),
) -> dict:
    """Simulate eight synthetic weeks; never writes assignments or agreements."""
    from datetime import timedelta

    household = service.get_household(payload.householdId)
    service._require_household_membership(payload.householdId, requester_member_id)
    members = service.ctx.members.list_by_household(payload.householdId)
    member_ids = [member.member_id for member in members]
    if not member_ids:
        from ...errors import ApiError
        raise ApiError("household_has_no_members", "Add household members before running the simulation.", 409)

    # Use the project's deterministic simulation provider as the scenario seed source.
    provider_type = type(service.sim_adapter.provider)
    scenario_provider = provider_type(seed=payload.seed)
    synthetic_members = scenario_provider.synthetic_members(payload.householdId, count=min(3, len(member_ids)))
    synthetic_profiles = {
        member_ids[index]: row.get("profile", {})
        for index, row in enumerate(synthetic_members)
        if index < len(member_ids)
    }
    rng = Random(payload.seed)
    source_tasks = [(item.task.strip(), float(item.estimatedEffort)) for item in payload.tasks]
    shareable = service.list_shareable_constraints(payload.householdId, requester_member_id)
    # Fixed anchor makes the seeded simulation reproducible across requests and machines.
    base_now = datetime(2025, 1, 6, tzinfo=UTC)
    solver_history: list[Assignment] = []
    round_robin_history: list[Assignment] = []
    solver_cumulative = {member_id: 0.0 for member_id in member_ids}
    round_robin_cumulative = {member_id: 0.0 for member_id in member_ids}
    weeks_output: list[dict] = []
    rr_offset = 0

    for week_index in range(payload.weeks):
        week_tasks = list(source_tasks)
        rng.shuffle(week_tasks)
        # Small deterministic variation represents a synthetic household week.
        week_tasks = [(name, max(5.0, effort + rng.randint(-5, 5))) for name, effort in week_tasks]
        solver_input = SolverInput(
            household_id=payload.householdId,
            member_ids=member_ids,
            constraints=shareable,
            task_efforts=[TaskEffort(task=name, estimated_effort=effort) for name, effort in week_tasks],
            availability={member.member_id: str(synthetic_profiles.get(member.member_id, {}).get("availability", "synthetic weekly availability")) for member in members},
            flexibility={member.member_id: 0.65 if synthetic_profiles.get(member.member_id, {}).get("schedule") == "flexible" else 0.5 for member in members},
            weights={member.member_id: 1.0 for member in members},
            existing_assignments=list(solver_history),
            horizon_days=21,
            preference_weight=payload.preferenceWeight,
        )
        solver_output = service.ctx.fairness_solver.generate_plan(solver_input)
        solver_week_load = {member_id: 0.0 for member_id in member_ids}
        solver_week_assignments: list[dict] = []
        for j, allocation in enumerate(solver_output.proposed_assignments):
            effort = float(allocation.estimated_effort)
            solver_week_load[allocation.member_id] += effort
            solver_cumulative[allocation.member_id] += effort
            solver_week_assignments.append({"task": allocation.task, "memberId": allocation.member_id, "estimatedEffort": round(effort, 1)})
            solver_history.append(Assignment(
                assignment_id=f"sim-solver-w{week_index + 1}-t{j + 1}", member_id=allocation.member_id, task=allocation.task,
                frequency="weekly", estimated_effort=effort, assigned_date=base_now + timedelta(days=week_index * 7), status=AssignmentStatus.COMPLETED,
            ))

        rr_week_load = {member_id: 0.0 for member_id in member_ids}
        rr_week_assignments: list[dict] = []
        for j, (task_name, effort) in enumerate(week_tasks):
            recipient = member_ids[(rr_offset + j) % len(member_ids)]
            rr_week_load[recipient] += effort
            round_robin_cumulative[recipient] += effort
            rr_week_assignments.append({"task": task_name, "memberId": recipient, "estimatedEffort": round(effort, 1)})
            round_robin_history.append(Assignment(
                assignment_id=f"sim-round-robin-w{week_index + 1}-t{j + 1}", member_id=recipient, task=task_name,
                frequency="weekly", estimated_effort=effort, assigned_date=base_now + timedelta(days=week_index * 7), status=AssignmentStatus.COMPLETED,
            ))
        rr_offset = (rr_offset + len(week_tasks)) % len(member_ids)
        solver_spread = round(max(solver_week_load.values()) - min(solver_week_load.values()), 1) if solver_week_load else 0.0
        rr_spread = round(max(rr_week_load.values()) - min(rr_week_load.values()), 1) if rr_week_load else 0.0
        weeks_output.append({
            "week": week_index + 1,
            "taskCount": len(week_tasks),
            "accord": {"workloadSpreadMinutes": solver_spread, "workloads": [{"memberId": mid, "minutes": round(solver_week_load[mid], 1)} for mid in member_ids], "assignments": solver_week_assignments},
            "roundRobin": {"workloadSpreadMinutes": rr_spread, "workloads": [{"memberId": mid, "minutes": round(rr_week_load[mid], 1)} for mid in member_ids], "assignments": rr_week_assignments},
        })

    def cumulative_rows(values: dict[str, float]) -> list[dict]:
        by_id = {member.member_id: member for member in members}
        return [{"memberId": mid, "displayName": by_id[mid].display_name, "minutes": round(values[mid], 1)} for mid in member_ids]

    solver_gap = round(max(solver_cumulative.values()) - min(solver_cumulative.values()), 1)
    rr_gap = round(max(round_robin_cumulative.values()) - min(round_robin_cumulative.values()), 1)
    return {
        "householdId": household.household_id, "weeks": weeks_output, "weeksSimulated": payload.weeks, "seed": payload.seed,
        "preferenceWeight": payload.preferenceWeight, "synthetic": True,
        "simulationSource": "packages/sim synthetic member profiles + seeded deterministic task variation",
        "syntheticProfiles": [
            {"memberId": member_id, "profile": synthetic_profiles.get(member_id, {})}
            for member_id in member_ids
        ],
        "accordCumulativeWorkloads": cumulative_rows(solver_cumulative),
        "roundRobinCumulativeWorkloads": cumulative_rows(round_robin_cumulative),
        "accordCumulativeGapMinutes": solver_gap, "roundRobinCumulativeGapMinutes": rr_gap,
        "headline": f"Simulation: Accord's heuristic cumulative gap is {solver_gap:g} min vs {rr_gap:g} min for round-robin.",
        "note": "Synthetic eight-week comparison only. Results are deterministic for the same seed and inputs, and the fairness solver is a heuristic, not a guarantee of fairness. No household records were written.",
    }
