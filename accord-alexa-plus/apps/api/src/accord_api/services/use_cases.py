"""Application use-cases orchestrating repositories and domain rules."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
import os

from ..errors import ApiError
from ..models import (
    AgreementStatus,
    AgreementVersion,
    Assignment,
    AssignmentStatus,
    ConsentStatus,
    Counteroffer,
    DerivedConstraint,
    DriftReport,
    DriftStatus,
    Expense,
    Household,
    InterviewStatus,
    Member,
    MediationSession,
    MonitoringSignal,
    PrivacyClassification,
    PrivacyStatus,
    PrivateInterviewSession,
    RenegotiationCycle,
    RenegotiationStatus,
)
from ..privacy import RESOURCE_NOT_FOUND
from ..solver_interface import SolverInput, TaskEffort
from ..utils import utcnow
from .context import AppContext
from .simulation_adapter import SimulationAdapter


class AccordService:
    def __init__(self, ctx: AppContext) -> None:
        self.ctx = ctx
        self.sim_adapter = SimulationAdapter()

    def _require_household(self, household_id: str) -> Household:
        household = self.ctx.households.get(household_id)
        if not household:
            raise RESOURCE_NOT_FOUND
        return household

    def _require_member(self, member_id: str) -> Member:
        member = self.ctx.members.get(member_id)
        if not member:
            raise RESOURCE_NOT_FOUND
        return member

    def _require_household_membership(self, household_id: str, requester_member_id: str) -> None:
        household = self._require_household(household_id)
        if requester_member_id not in {m.member_id for m in household.members}:
            raise RESOURCE_NOT_FOUND

    def create_household(self, name: str, scenario_metadata: dict[str, str]) -> Household:
        household = Household(
            household_id=self.ctx.id_gen.next("household"),
            name=name,
            scenario_metadata=dict(scenario_metadata),
        )
        return self.ctx.households.create(household)

    def get_household(self, household_id: str) -> Household:
        return self._require_household(household_id)

    def add_member(
        self,
        household_id: str,
        display_name: str,
        role: str,
        consent_status: ConsentStatus = ConsentStatus.PENDING,
        privacy_status: PrivacyStatus = PrivacyStatus.PRIVATE_ONLY,
    ) -> Member:
        household = self._require_household(household_id)
        member = Member(
            member_id=self.ctx.id_gen.next("member"),
            display_name=display_name,
            role=role,
            consent_status=consent_status,
            privacy_status=privacy_status,
        )
        self.ctx.members.add(household_id, member)
        household.add_member(member)
        return member

    def list_members(self, household_id: str) -> list[Member]:
        self._require_household(household_id)
        return self.ctx.members.list_by_household(household_id)

    def update_member_consent(
        self,
        household_id: str,
        member_id: str,
        requester_member_id: str,
        consent_status: ConsentStatus,
    ) -> Member:
        """Allow a member to change only their own consent record."""
        household = self._require_household(household_id)
        member = self._require_member(member_id)
        if member_id != requester_member_id:
            raise RESOURCE_NOT_FOUND
        if member_id not in {candidate.member_id for candidate in household.members}:
            raise RESOURCE_NOT_FOUND
        member.consent_status = consent_status
        return member

    def start_interview(self, household_id: str, member_id: str) -> PrivateInterviewSession:
        household = self._require_household(household_id)
        member = self._require_member(member_id)
        if member_id not in {candidate.member_id for candidate in household.members}:
            raise RESOURCE_NOT_FOUND
        if member.consent_status != ConsentStatus.GRANTED:
            raise ApiError(
                "consent_required",
                "The member must grant consent before starting a private interview.",
                409,
            )
        session = PrivateInterviewSession(
            session_id=self.ctx.id_gen.next("session"),
            household_id=household_id,
            member_id=member_id,
            status=InterviewStatus.STARTED,
        )
        return self.ctx.interviews.create(session)

    def submit_interview(
        self,
        session_id: str,
        requester_member_id: str,
        transcript_reference: str,
        answers: dict[str, str] | None = None,
    ) -> PrivateInterviewSession:
        session = self.ctx.interviews.get(session_id)
        if not session:
            raise RESOURCE_NOT_FOUND
        if session.member_id != requester_member_id:
            raise RESOURCE_NOT_FOUND
        member = self._require_member(session.member_id)
        if member.consent_status != ConsentStatus.GRANTED:
            raise ApiError("consent_required", "Consent is not currently granted.", 409)
        session.private_answers = {
            str(key): str(value).strip()[:2000]
            for key, value in (answers or {}).items()
            if str(value).strip()
        }
        session.transcript_reference = transcript_reference
        session.transition(InterviewStatus.SUBMITTED)
        return self.ctx.interviews.update(session)

    def complete_interview(self, session_id: str, requester_member_id: str) -> PrivateInterviewSession:
        session = self.ctx.interviews.get(session_id)
        if not session:
            raise RESOURCE_NOT_FOUND
        if session.member_id != requester_member_id:
            raise RESOURCE_NOT_FOUND
        member = self._require_member(session.member_id)
        if member.consent_status != ConsentStatus.GRANTED:
            raise ApiError("consent_required", "Consent is not currently granted.", 409)
        session.transition(InterviewStatus.COMPLETED)
        return self.ctx.interviews.update(session)

    def get_private_interview(
        self, session_id: str, requester_member_id: str
    ) -> PrivateInterviewSession:
        session = self.ctx.interviews.get(session_id)
        if not session or session.member_id != requester_member_id:
            raise RESOURCE_NOT_FOUND
        return session

    def derive_constraints(
        self, session_id: str, requester_member_id: str
    ) -> list[DerivedConstraint]:
        session = self.get_private_interview(session_id, requester_member_id)
        member = self._require_member(session.member_id)
        if member.consent_status != ConsentStatus.GRANTED:
            raise ApiError("consent_required", "Consent is not currently granted.", 409)
        if session.status != InterviewStatus.COMPLETED:
            raise ApiError("interview_not_completed", "Interview must be completed first.", 409)

        # Derivation is idempotent: repeated requests return the constraints
        # already created for this private session instead of duplicating them.
        if session.extracted_constraint_references:
            return self.ctx.constraints.list_by_ids(session.extracted_constraint_references)

        # Rule-based summaries use category-level results rather than copying
        # private free text into shareable constraints.
        answer_text = " ".join(session.private_answers.values()).casefold()
        shareable_summary = "prefers a balanced weekly chore load"
        category = "task_preference"
        if any(word in answer_text for word in ("expense", "bill", "rent", "cost", "money")):
            category = "expense_preference"
            shareable_summary = "wants shared expenses to follow a clear, agreed rule"
        elif any(word in answer_text for word in ("schedule", "time", "busy", "availability", "weekday")):
            category = "availability"
            shareable_summary = "needs household duties to account for individual availability"
        elif any(word in answer_text for word in ("dish", "kitchen", "cook", "clean", "chore")):
            category = "task_preference"
            shareable_summary = "has expressed preferences about the distribution of household tasks"

        derived: list[DerivedConstraint] = [
            DerivedConstraint(
                constraint_id=self.ctx.id_gen.next("constraint"),
                household_id=session.household_id,
                member_id=session.member_id,
                category=category,
                preference_or_requirement=shareable_summary,
                importance_weight=0.7,
                flexibility=0.5,
                privacy_classification=PrivacyClassification.SHAREABLE_DERIVED,
                source_session_reference=session.session_id,
            ),
            DerivedConstraint(
                constraint_id=self.ctx.id_gen.next("constraint"),
                household_id=session.household_id,
                member_id=session.member_id,
                category="private_context",
                preference_or_requirement="private context retained in member scope",
                importance_weight=0.6,
                flexibility=0.4,
                privacy_classification=PrivacyClassification.PRIVATE,
                source_session_reference=session.session_id,
            ),
        ]
        self.ctx.constraints.create_many(derived)
        session.extracted_constraint_references.extend([c.constraint_id for c in derived])
        self.ctx.interviews.update(session)
        return derived

    def list_member_constraints(
        self, member_id: str, requester_member_id: str
    ) -> list[DerivedConstraint]:
        if member_id != requester_member_id:
            raise RESOURCE_NOT_FOUND
        return self.ctx.constraints.list_by_member(member_id)

    def list_shareable_constraints(
        self, household_id: str, requester_member_id: str
    ) -> list[DerivedConstraint]:
        self._require_household_membership(household_id, requester_member_id)
        consented_member_ids = {
            member.member_id
            for member in self.ctx.members.list_by_household(household_id)
            if member.consent_status == ConsentStatus.GRANTED
        }
        return [
            constraint
            for constraint in self.ctx.constraints.list_shareable_by_household(household_id)
            if constraint.privacy_classification == PrivacyClassification.SHAREABLE_DERIVED
            and constraint.member_id in consented_member_ids
        ]

    def generate_agreement_proposal(
        self, household_id: str, requester_member_id: str, derived_constraint_ids: list[str]
    ) -> AgreementVersion:
        self._require_household_membership(household_id, requester_member_id)
        household = self._require_household(household_id)
        if any(member.consent_status != ConsentStatus.GRANTED for member in household.members):
            raise ApiError(
                "consent_required",
                "Every household member must grant consent before generating a shared proposal.",
                409,
            )
        household_member_ids = {member.member_id for member in household.members}
        constraints = [
            c
            for c in self.ctx.constraints.list_by_ids(derived_constraint_ids)
            if c.privacy_classification == PrivacyClassification.SHAREABLE_DERIVED
            and c.household_id == household_id
            and c.member_id in household_member_ids
            and self._require_member(c.member_id).consent_status == ConsentStatus.GRANTED
        ]

        if not constraints:
            raise ApiError("missing_constraints", "No shareable derived constraints provided.", 400)

        solver_input = SolverInput(
            household_id=household_id,
            member_ids=[m.member_id for m in household.members],
            constraints=constraints,
            task_efforts=[
                TaskEffort(task="dishes", estimated_effort=30.0),
                TaskEffort(task="trash", estimated_effort=20.0),
                TaskEffort(task="bathroom", estimated_effort=40.0),
            ],
            availability={m.member_id: "weekly" for m in household.members},
            flexibility={m.member_id: 0.5 for m in household.members},
            weights={m.member_id: 1.0 for m in household.members},
            existing_assignments=self.ctx.assignments.list_by_household(household_id),
            horizon_days=14,
        )
        proposal = self.ctx.fairness_solver.generate_plan(solver_input)

        agreement = AgreementVersion(
            agreement_id=self.ctx.id_gen.next("agreement"),
            household_id=household_id,
            version=1,
            status=AgreementStatus.DRAFT,
            proposal=[],
            fairness_score=proposal.fairness_score,
            rationale=proposal.rationale,
        )
        agreement.transition(AgreementStatus.PROPOSED)

        assignments: list[Assignment] = []
        for proposed in proposal.proposed_assignments:
            assignments.append(
                Assignment(
                    assignment_id=self.ctx.id_gen.next("assignment"),
                    member_id=proposed.member_id,
                    task=proposed.task,
                    frequency=proposed.frequency,
                    estimated_effort=proposed.estimated_effort,
                    assigned_date=proposed.assigned_date,
                    status=AssignmentStatus.SCHEDULED,
                )
            )
        agreement.proposal = assignments

        self.ctx.agreements.create(agreement)
        self.ctx.assignments.create_many(assignments)
        self.ctx.assignments.link_to_household(household_id, [a.assignment_id for a in assignments])
        self.ctx.assignments.link_to_agreement(
            agreement.agreement_id, agreement.version, [a.assignment_id for a in assignments]
        )
        return agreement

    def compare_fairness(
        self,
        household_id: str,
        requester_member_id: str,
        task_efforts: list[tuple[str, float]],
        preference_weight: float,
    ) -> dict:
        """Return a read-only comparison of Accord's solver and round-robin baseline."""
        household = self._require_household(household_id)
        self._require_household_membership(household_id, requester_member_id)
        members = self.ctx.members.list_by_household(household_id)
        member_ids = [member.member_id for member in members]
        if not members:
            raise ApiError("household_has_no_members", "Add at least one household member before comparing plans.", 409)
        tasks = [TaskEffort(task=name.strip(), estimated_effort=float(effort)) for name, effort in task_efforts if name.strip() and float(effort) > 0]
        if not tasks:
            raise ApiError("no_valid_tasks", "Provide at least one task with positive estimated effort.", 422)
        # The repository helper filters out private constraints and constraints
        # belonging to members whose consent has been revoked or is pending.
        constraints = self.list_shareable_constraints(household_id, requester_member_id)
        existing = self.ctx.assignments.list_by_household(household_id)
        now = utcnow()
        current_load = {member_id: 0.0 for member_id in member_ids}
        for assignment in existing:
            if assignment.member_id not in current_load or assignment.estimated_effort <= 0:
                continue
            weight = 0.35 if assignment.status == AssignmentStatus.COMPLETED else 1.0
            try:
                age_days = (now - assignment.assigned_date).total_seconds() / 86400
            except (TypeError, ValueError):
                age_days = 0
            if age_days > 0:
                weight *= max(0.25, 1.0 - age_days / 14)
            current_load[assignment.member_id] += float(assignment.estimated_effort) * weight

        solver_input = SolverInput(
            household_id=household_id,
            member_ids=member_ids,
            constraints=constraints,
            task_efforts=tasks,
            availability={m.member_id: "weekly" for m in members},
            flexibility={m.member_id: 0.5 for m in members},
            weights={m.member_id: 1.0 for m in members},
            existing_assignments=existing,
            horizon_days=14,
            preference_weight=max(0.0, min(1.0, float(preference_weight))),
        )
        solver_output = self.ctx.fairness_solver.generate_plan(solver_input)
        round_robin = []
        round_counts = {member_id: 0 for member_id in member_ids}
        for index, task in enumerate(tasks):
            member_id = member_ids[index % len(member_ids)]
            round_counts[member_id] += 1
            round_robin.append({"task": task.task, "memberId": member_id, "estimatedEffort": float(task.estimated_effort)})

        def shape_result(assignments: list[dict], algorithm: str) -> dict:
            load = dict(current_load)
            task_names = {member_id: [] for member_id in member_ids}
            for item in assignments:
                load[item["memberId"]] += float(item["estimatedEffort"])
                task_names[item["memberId"]].append(item["task"])
            spread = max(load.values()) - min(load.values()) if load else 0.0
            denominator = max(sum(load.values()), sum(task.estimated_effort for task in tasks), 1.0)
            score = round(max(0.0, min(1.0, 1.0 - spread / denominator)), 2)
            by_member = []
            for member in members:
                minutes = round(load[member.member_id], 1)
                assigned_names = task_names[member.member_id]
                assigned_text = ", ".join(assigned_names) if assigned_names else "no new tasks"
                if algorithm == "Accord workload-aware solver":
                    explanation = (
                        f"Projected workload is {minutes:g} minutes, including {assigned_text}, after accounting for recent workload. "
                        f"Accord considered permitted shareable constraints with preference influence at {round(preference_weight * 100)}%; this is a heuristic, not a guarantee of fairness."
                    )
                else:
                    explanation = (
                        f"Projected workload is {minutes:g} minutes, including {assigned_text}, under a simple repeating task order. "
                        "This baseline does not consider preferences or prior workload when choosing each new task and is not a measure of personal fairness."
                    )
                by_member.append({
                    "memberId": member.member_id,
                    "displayName": member.display_name,
                    "projectedMinutes": minutes,
                    "assignedTasks": assigned_names,
                    "explanation": explanation,
                })
            return {
                "algorithm": algorithm,
                "fairnessScore": score,
                "workloadSpreadMinutes": round(spread, 1),
                "workloads": by_member,
                "assignments": assignments,
            }

        solver_assignments = [
            {"task": assignment.task, "memberId": assignment.member_id, "estimatedEffort": assignment.estimated_effort}
            for assignment in solver_output.proposed_assignments
        ]
        return {
            "householdId": household_id,
            "preferenceWeight": max(0.0, min(1.0, float(preference_weight))),
            "taskCount": len(tasks),
            "shareablePreferencesUsed": [{"memberId": c.member_id, "category": c.category, "preference": c.preference_or_requirement} for c in constraints],
            "note": "Preview only: no assignments or agreement records were saved. Scores are heuristics, not a guarantee of fairness.",
            "solver": shape_result(solver_assignments, "Accord workload-aware solver"),
            "roundRobin": shape_result(round_robin, "Round-robin baseline"),
        }

    def get_agreement(self, agreement_id: str, version: int) -> AgreementVersion:
        agreement = self.ctx.agreements.get(agreement_id, version)
        if not agreement:
            raise RESOURCE_NOT_FOUND
        return agreement

    def get_agreement_history(self, agreement_id: str) -> list[AgreementVersion]:
        versions = self.ctx.agreements.list_versions(agreement_id)
        if not versions:
            raise RESOURCE_NOT_FOUND
        return versions

    def list_household_agreements(
        self, household_id: str, requester_member_id: str
    ) -> list[AgreementVersion]:
        self._require_household_membership(household_id, requester_member_id)
        return self.ctx.agreements.list_by_household(household_id)

    def get_agreement_for_member(
        self, agreement_id: str, version: int, requester_member_id: str
    ) -> AgreementVersion:
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(agreement.household_id, requester_member_id)
        return agreement

    def get_agreement_history_for_member(
        self, agreement_id: str, requester_member_id: str
    ) -> list[AgreementVersion]:
        versions = self.get_agreement_history(agreement_id)
        self._require_household_membership(versions[0].household_id, requester_member_id)
        return versions

    def submit_draft_agreement(
        self, agreement_id: str, version: int, requester_member_id: str
    ) -> AgreementVersion:
        """Submit an explicit draft into the normal member approval workflow."""
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(agreement.household_id, requester_member_id)
        if agreement.status != AgreementStatus.DRAFT:
            raise ApiError("invalid_draft_state", "Only a draft agreement can be submitted for member review.", 409)
        agreement.transition(AgreementStatus.PROPOSED)
        return self.ctx.agreements.update(agreement)

    def approve_agreement(
        self, agreement_id: str, version: int, requester_member_id: str
    ) -> AgreementVersion:
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(agreement.household_id, requester_member_id)
        agreement.register_approval(requester_member_id)
        household = self._require_household(agreement.household_id)
        if set(agreement.approvals) >= {m.member_id for m in household.members}:
            if agreement.status == AgreementStatus.PROPOSED:
                agreement.transition(AgreementStatus.APPROVED)
        return self.ctx.agreements.update(agreement)


    def veto_agreement(
        self, agreement_id: str, version: int, requester_member_id: str
    ) -> AgreementVersion:
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(
            agreement.household_id, requester_member_id
        )

        agreement.register_veto(requester_member_id)

        if agreement.status in (
            AgreementStatus.PROPOSED,
            AgreementStatus.CHANGES_REQUESTED,
        ):
            agreement.transition(AgreementStatus.VETOED)

        return self.ctx.agreements.update(agreement)



    def counteroffer_agreement(
        self, agreement_id: str, version: int, requester_member_id: str, message: str
    ) -> AgreementVersion:
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(agreement.household_id, requester_member_id)
        agreement.register_counteroffer(
            Counteroffer(member_id=requester_member_id, message=message, submitted_at=utcnow())
        )
        if agreement.status == AgreementStatus.PROPOSED:
            agreement.transition(AgreementStatus.CHANGES_REQUESTED)
        return self.ctx.agreements.update(agreement)

    def activate_agreement(self, agreement_id: str, version: int, requester_member_id: str) -> AgreementVersion:
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(agreement.household_id, requester_member_id)
        household = self._require_household(agreement.household_id)
        required_approvals = {member.member_id for member in household.members}
        if any(member.consent_status != ConsentStatus.GRANTED for member in household.members):
            raise ApiError("consent_required", "Every household member must currently have consent granted.", 409)
        if agreement.status != AgreementStatus.APPROVED or not required_approvals.issubset(set(agreement.approvals)):
            raise ApiError("invalid_activation_state", "Agreement cannot be activated from current state.", 409)
        agreement.transition(AgreementStatus.ACTIVE)
        return self.ctx.agreements.update(agreement)

    def create_assignment(
        self,
        household_id: str,
        requester_member_id: str,
        member_id: str,
        task: str,
        frequency: str,
        estimated_effort: float,
        assigned_date: datetime,
    ) -> Assignment:
        self._require_household_membership(household_id, requester_member_id)
        household = self._require_household(household_id)
        if member_id not in {member.member_id for member in household.members}:
            raise RESOURCE_NOT_FOUND
        assignment = Assignment(
            assignment_id=self.ctx.id_gen.next("assignment"),
            member_id=member_id,
            task=task,
            frequency=frequency,
            estimated_effort=estimated_effort,
            assigned_date=assigned_date,
            status=AssignmentStatus.SCHEDULED,
        )
        self.ctx.assignments.create(assignment)
        self.ctx.assignments.link_to_household(household_id, [assignment.assignment_id])
        return assignment

    def list_assignments(self, household_id: str, requester_member_id: str) -> list[Assignment]:
        self._require_household_membership(household_id, requester_member_id)
        return self.ctx.assignments.list_by_household(household_id)

    def reassign_assignment(self, assignment_id: str, requester_member_id: str, target_member_id: str) -> Assignment:
        """Perform an explicitly confirmed task reassignment within the household."""
        assignment = self.ctx.assignments.get(assignment_id)
        if assignment is None:
            raise RESOURCE_NOT_FOUND
        household_id = next(
            (household_id for household_id in self.ctx.households._items if any(
                item.assignment_id == assignment_id for item in self.ctx.assignments.list_by_household(household_id)
            )),
            None,
        )
        if household_id is None:
            raise RESOURCE_NOT_FOUND
        household = self._require_household(household_id)
        self._require_household_membership(household_id, requester_member_id)
        if target_member_id not in {member.member_id for member in household.members}:
            raise RESOURCE_NOT_FOUND
        return self.ctx.assignments.reassign(assignment, target_member_id)

    def update_assignment_status(
        self, assignment_id: str, requester_member_id: str, status: AssignmentStatus
    ) -> Assignment:
        assignment = self.ctx.assignments.get(assignment_id)
        if not assignment:
            raise RESOURCE_NOT_FOUND
        # allow only assigned member to mark progress; hide otherwise
        if assignment.member_id != requester_member_id:
            raise RESOURCE_NOT_FOUND
        if status == AssignmentStatus.COMPLETED and assignment.status != AssignmentStatus.COMPLETED:
            assignment.completed_at = utcnow()
        elif status != AssignmentStatus.COMPLETED:
            assignment.completed_at = None
        assignment.status = status
        return self.ctx.assignments.update(assignment)

    def create_expense(
        self,
        household_id: str,
        requester_member_id: str,
        payer_member_id: str,
        description: str,
        amount: float,
        category: str,
        expense_date: datetime,
        split_member_ids: list[str] | None = None,
        split_ratios: dict[str, int] | None = None,
    ) -> Expense:
        household = self._require_household(household_id)
        self._require_household_membership(household_id, requester_member_id)
        household_member_ids = {member.member_id for member in household.members}
        if payer_member_id not in household_member_ids:
            raise RESOURCE_NOT_FOUND
        cleaned_description = description.strip()
        cleaned_category = category.strip()
        if not cleaned_description or not cleaned_category or amount <= 0:
            raise ApiError("invalid_expense", "Expense description, category, and positive amount are required.", 422)
        beneficiaries = list(split_member_ids) if split_member_ids is not None else list(household_member_ids)
        if not beneficiaries or len(beneficiaries) != len(set(beneficiaries)) or not set(beneficiaries).issubset(household_member_ids):
            raise ApiError("invalid_expense_split", "Split members must be a non-empty, unique subset of this household.", 422)
        ratios = dict(split_ratios or {})
        if ratios and (set(ratios) != set(beneficiaries) or any(type(weight) is not int or weight <= 0 for weight in ratios.values())):
            raise ApiError("invalid_expense_ratios", "Provide a positive integer split ratio for every beneficiary, and no other member.", 422)
        expense = Expense(
            expense_id=self.ctx.id_gen.next("expense"),
            household_id=household_id,
            payer_member_id=payer_member_id,
            description=cleaned_description,
            amount=round(float(amount), 2),
            category=cleaned_category,
            expense_date=expense_date,
            split_member_ids=beneficiaries,
            split_ratios=ratios,
        )
        return self.ctx.expenses.create(expense)

    def list_expenses(self, household_id: str, requester_member_id: str) -> list[Expense]:
        self._require_household_membership(household_id, requester_member_id)
        return self.ctx.expenses.list_by_household(household_id)

    def calculate_settle_up(self, household_id: str, requester_member_id: str) -> dict:
        """Suggest minimal transfers using each expense's participant subset and weights.

        Money is tracked as integer cents. Fractional cents are assigned by largest
        remainder, then stable member ID, so every expense allocation sums exactly.
        This method never initiates or records a payment.
        """
        household = self._require_household(household_id)
        self._require_household_membership(household_id, requester_member_id)
        members = self.ctx.members.list_by_household(household_id)
        if not members:
            raise ApiError("household_has_no_members", "Add household members before calculating settlement.", 409)
        expenses = self.ctx.expenses.list_by_household(household_id)
        member_ids = [member.member_id for member in members]
        member_id_set = set(member_ids)
        paid_cents = {member_id: 0 for member_id in member_ids}
        owed_cents = {member_id: 0 for member_id in member_ids}
        total_cents = 0
        split_summary: list[dict] = []
        for expense in expenses:
            cents = int(round(float(expense.amount) * 100))
            if cents <= 0:
                continue
            total_cents += cents
            if expense.payer_member_id in paid_cents:
                paid_cents[expense.payer_member_id] += cents
            raw_beneficiaries = expense.split_member_ids or member_ids
            beneficiaries = sorted(set(raw_beneficiaries).intersection(member_id_set))
            if not beneficiaries:
                # Corrupt/legacy split data should not make balances disappear.
                beneficiaries = sorted(member_ids)
            ratios = expense.split_ratios if expense.split_ratios and set(expense.split_ratios) == set(beneficiaries) else {mid: 1 for mid in beneficiaries}
            weight_total = sum(ratios.values())
            raw_shares = {mid: cents * ratios[mid] / weight_total for mid in beneficiaries}
            base_shares = {mid: (cents * ratios[mid]) // weight_total for mid in beneficiaries}
            leftover = cents - sum(base_shares.values())
            remainder_order = sorted(beneficiaries, key=lambda mid: (-(raw_shares[mid] - base_shares[mid]), mid))
            for mid in remainder_order[:leftover]:
                base_shares[mid] += 1
            for mid, share in base_shares.items():
                owed_cents[mid] += share
            split_summary.append({
                "expenseId": expense.expense_id,
                "description": expense.description,
                "amount": round(cents / 100, 2),
                "includedMemberIds": beneficiaries,
                "weights": ratios,
                "shares": [{"memberId": mid, "amountCents": base_shares[mid]} for mid in beneficiaries],
            })

        net = {mid: paid_cents[mid] - owed_cents[mid] for mid in member_ids}
        # Net amounts must zero-sum exactly in integer cents.
        if sum(net.values()) != 0:
            raise ApiError("settlement_invariant_failed", "Expense split balances did not net to zero; review stored split data.", 500)
        debtors = [[mid, -amount] for mid, amount in sorted(net.items()) if amount < 0]
        creditors = [[mid, amount] for mid, amount in sorted(net.items()) if amount > 0]
        transfers: list[dict] = []
        debtor_index = creditor_index = 0
        while debtor_index < len(debtors) and creditor_index < len(creditors):
            from_id, owing = debtors[debtor_index]
            to_id, due = creditors[creditor_index]
            amount = min(owing, due)
            if amount > 0:
                transfers.append({"fromMemberId": from_id, "toMemberId": to_id, "amount": round(amount / 100, 2)})
            debtors[debtor_index][1] -= amount
            creditors[creditor_index][1] -= amount
            if debtors[debtor_index][1] == 0:
                debtor_index += 1
            if creditors[creditor_index][1] == 0:
                creditor_index += 1
        by_id = {member.member_id: member for member in members}
        balances = []
        for mid in member_ids:
            balance = net[mid] / 100
            balances.append({
                "memberId": mid,
                "displayName": by_id[mid].display_name,
                "paid": round(paid_cents[mid] / 100, 2),
                "fairShare": round(owed_cents[mid] / 100, 2),
                "netBalance": round(balance, 2),
                "direction": "receive" if balance > 0 else "pay" if balance < 0 else "settled",
            })
        return {
            "householdId": household.household_id,
            "householdName": household.name,
            "method": "weighted_subset_split_and_minimal_transfers",
            "totalExpenses": round(total_cents / 100, 2),
            "memberCount": len(members),
            "balances": balances,
            "transfers": transfers,
            "expenseSplits": split_summary,
            "netBalanceCents": sum(net.values()),
            "note": "Suggestion only. Each expense uses its configured participant subset and integer split weights; unspecified splits include the whole household equally. Remainder cents use largest fractional remainder then member ID. No payment has been initiated or marked complete.",
        }

    def workload_drift_alert(self, household_id: str, requester_member_id: str, threshold: float | None = None) -> dict:
        """Find a completed-work imbalance from recorded assignments in the last 21 days."""
        household = self._require_household(household_id)
        self._require_household_membership(household_id, requester_member_id)
        if threshold is None:
            try:
                threshold = float(os.getenv("ACCORD_WORKLOAD_DRIFT_THRESHOLD", "0.40"))
            except ValueError:
                threshold = 0.40
        threshold = max(0.1, min(1.0, float(threshold)))
        now = utcnow()
        start = now - timedelta(days=21)
        members = self.ctx.members.list_by_household(household_id)
        minutes = {member.member_id: 0.0 for member in members}
        for assignment in self.ctx.assignments.list_by_household(household_id):
            if assignment.status != AssignmentStatus.COMPLETED or assignment.member_id not in minutes:
                continue
            # New completions use their real completion timestamp. Legacy records
            # without one fall back to assigned_date and are disclosed in the response.
            timestamp = assignment.completed_at or assignment.assigned_date
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=UTC)
            if start <= timestamp <= now:
                minutes[assignment.member_id] += max(0.0, float(assignment.estimated_effort))
        total = sum(minutes.values())
        by_id = {member.member_id: member for member in members}
        shares = [{"memberId": mid, "displayName": by_id[mid].display_name, "completedMinutes": round(value, 1), "share": round(value / total, 4) if total else 0.0} for mid, value in minutes.items()]
        top = max(shares, key=lambda row: (row["share"], row["memberId"])) if shares else None
        alert = None
        if top and total > 0 and top["share"] > threshold:
            alert = {
                "memberId": top["memberId"], "displayName": top["displayName"],
                "share": top["share"], "completedMinutes": top["completedMinutes"],
                "threshold": threshold,
                "message": f"{top['displayName']} completed {top['share']:.0%} of recorded work in the last 3 weeks, above the {threshold:.0%} review threshold.",
                "suggestion": "Consider a gentle household check-in and draft a rebalance together; this signal is not a judgment and does not reassign tasks.",
            }
        legacy_count = sum(1 for assignment in self.ctx.assignments.list_by_household(household_id) if assignment.status == AssignmentStatus.COMPLETED and assignment.completed_at is None)
        note = "On-demand workload drift heuristic from completed tasks only. No notification was sent and no assignment was changed."
        if legacy_count:
            note += f" {legacy_count} legacy completed task(s) have no completion timestamp, so their assignment date is used as a fallback."
        return {"householdId": household.household_id, "windowDays": 21, "threshold": threshold, "totalCompletedMinutes": round(total, 1), "memberShares": shares, "alert": alert, "mode": "completion timestamp (assigned date for legacy tasks without completedAt)", "note": note}

    def weekly_digest(self, household_id: str, requester_member_id: str) -> dict:
        """Build an on-demand seven-day household summary from recorded demo data."""
        household = self._require_household(household_id)
        self._require_household_membership(household_id, requester_member_id)
        now = utcnow()
        start = now - timedelta(days=7)
        assignments = self.ctx.assignments.list_by_household(household_id)
        recent_assignments = []
        for assignment in assignments:
            try:
                assigned_at = assignment.assigned_date
                if assigned_at.tzinfo is None:
                    assigned_at = assigned_at.replace(tzinfo=UTC)
                if assigned_at >= start:
                    recent_assignments.append(assignment)
            except (TypeError, ValueError):
                continue
        recent_expenses = []
        for expense in self.ctx.expenses.list_by_household(household_id):
            expense_date = expense.expense_date
            if expense_date.tzinfo is None:
                expense_date = expense_date.replace(tzinfo=UTC)
            if expense_date >= start:
                recent_expenses.append(expense)
        agreements = self.ctx.agreements.list_by_household(household_id)
        pending_agreements = [a for a in agreements if a.status in {AgreementStatus.PROPOSED, AgreementStatus.CHANGES_REQUESTED}]
        open_drifts = [r for r in self.ctx.drift_reports.list_by_household(household_id) if r.status == DriftStatus.OPEN]
        completed = sum(a.status == AssignmentStatus.COMPLETED for a in recent_assignments)
        missed = sum(a.status == AssignmentStatus.MISSED for a in recent_assignments)
        open_tasks = sum(a.status != AssignmentStatus.COMPLETED for a in assignments)
        expenses_total = sum(float(e.amount) for e in recent_expenses)
        workload_drift = self.workload_drift_alert(household_id, requester_member_id)
        insights: list[str] = []
        if workload_drift.get("alert"):
            insights.append(workload_drift["alert"]["message"] + " " + workload_drift["alert"]["suggestion"])
        if missed:
            insights.append(f"{missed} task(s) are marked missed; consider revisiting the schedule rather than assigning blame.")
        if pending_agreements:
            insights.append(f"{len(pending_agreements)} agreement proposal(s) still need household decisions.")
        if open_drifts:
            insights.append(f"{len(open_drifts)} open monitoring report(s) may deserve a voluntary check-in.")
        if not insights:
            insights.append("No urgent issue was identified from the recorded demo data. Ask members whether the plan still feels workable.")
        return {
            "householdId": household_id,
            "householdName": household.name,
            "generatedAt": now.isoformat(),
            "windowDays": 7,
            "summary": {
                "members": len(self.ctx.members.list_by_household(household_id)),
                "tasksInWindow": len(recent_assignments),
                "completedInWindow": completed,
                "openTasks": open_tasks,
                "missedTasks": missed,
                "expensesInWindow": len(recent_expenses),
                "expensesTotal": round(expenses_total, 2),
                "pendingAgreements": len(pending_agreements),
                "openDriftReports": len(open_drifts),
            },
            "insights": insights,
            "workloadDrift": workload_drift,
            "dataNote": "Generated from recorded prototype data; monitoring signals may be simulated. No automatic notifications were sent.",
        }

    def record_monitoring_signal(
        self,
        household_id: str,
        requester_member_id: str,
        assignment_reference: str,
        member_reference: str,
        expected_contribution: float,
        observed_contribution: float,
        timestamp: datetime,
    ) -> MonitoringSignal:
        self._require_household_membership(household_id, requester_member_id)
        household = self._require_household(household_id)
        household_member_ids = {member.member_id for member in household.members}
        if member_reference not in household_member_ids:
            raise RESOURCE_NOT_FOUND
        assignment = self.ctx.assignments.get(assignment_reference)
        if not assignment or assignment.member_id != member_reference:
            raise RESOURCE_NOT_FOUND
        signal = MonitoringSignal(
            signal_id=self.ctx.id_gen.next("signal"),
            assignment_reference=assignment_reference,
            member_reference=member_reference,
            expected_contribution=expected_contribution,
            observed_contribution=observed_contribution,
            timestamp=timestamp,
        )
        self.ctx.monitoring.create(signal, household_id)
        return signal

    def list_monitoring_signals(
        self, household_id: str, requester_member_id: str
    ) -> list[MonitoringSignal]:
        self._require_household_membership(household_id, requester_member_id)
        return self.ctx.monitoring.list_by_household(household_id)

    def generate_drift_report(
        self, agreement_id: str, version: int, requester_member_id: str
    ) -> DriftReport:
        agreement = self.get_agreement(agreement_id, version)
        self._require_household_membership(agreement.household_id, requester_member_id)
        signals = self.ctx.monitoring.list_by_household(agreement.household_id)
        severity, affected_members, evidence, action = self.ctx.drift_service.evaluate(signals)
        affected_assignments = sorted({signal.assignment_reference for signal in signals if signal.expected_contribution > signal.observed_contribution})
        report = DriftReport(
            drift_id=self.ctx.id_gen.next("drift"),
            agreement_version_reference=f"{agreement_id}:v{version}",
            affected_members=affected_members,
            detected_signals=[signal.signal_id for signal in signals],
            severity=severity,
            explanation="Deterministic deviation analysis over expected vs observed contributions.",
            recommended_action=action,
            evidence=evidence,
            affected_assignments=affected_assignments,
            status=DriftStatus.OPEN,
        )
        self.ctx.drift_reports.create(report, agreement.household_id)
        return report

    def get_drift_report(self, drift_id: str, requester_member_id: str) -> DriftReport:
        report = self.ctx.drift_reports.get(drift_id)
        if not report:
            raise RESOURCE_NOT_FOUND
        agreement_id = report.agreement_version_reference.split(":")[0]
        versions = self.ctx.agreements.list_versions(agreement_id)
        if not versions:
            raise RESOURCE_NOT_FOUND
        household_id = versions[0].household_id
        self._require_household_membership(household_id, requester_member_id)
        return report

    def start_renegotiation(
        self, household_id: str, drift_id: str, requester_member_id: str
    ) -> tuple[RenegotiationCycle, list[PrivateInterviewSession]]:
        self._require_household_membership(household_id, requester_member_id)
        report = self.get_drift_report(drift_id, requester_member_id)
        agreement_id = report.agreement_version_reference.split(":")[0]
        agreement_versions = self.ctx.agreements.list_versions(agreement_id)
        if not agreement_versions or agreement_versions[0].household_id != household_id:
            raise RESOURCE_NOT_FOUND
        household = self._require_household(household_id)
        if any(member.consent_status != ConsentStatus.GRANTED for member in household.members):
            raise ApiError("consent_required", "Every member must have consent granted before renegotiation interviews start.", 409)

        cycle = RenegotiationCycle(
            renegotiation_id=self.ctx.id_gen.next("renegotiation"),
            household_id=household_id,
            drift_id=drift_id,
            status=RenegotiationStatus.REQUESTED,
        )
        cycle.transition(RenegotiationStatus.INTERVIEWING)
        self.ctx.renegotiations.create(cycle)

        sessions: list[PrivateInterviewSession] = []
        for member in self.ctx.members.list_by_household(household_id):
            sessions.append(self.start_interview(household_id=household_id, member_id=member.member_id))
        return cycle, sessions

    def demo_roommates_reset(self) -> dict:
        self.ctx.reset()

        household_data = self.sim_adapter.provider.synthetic_household("demo-household", "Accord Demo Home")
        household = self.create_household(
            name=household_data["name"], scenario_metadata=household_data["scenarioMetadata"]
        )

        members_data = self.sim_adapter.provider.synthetic_members(household.household_id, count=3)
        created_members: list[Member] = []
        for m in members_data:
            created_members.append(
                self.add_member(
                    household_id=household.household_id,
                    display_name=m["displayName"],
                    role=m["role"],
                    consent_status=ConsentStatus(m.get("consentStatus", "granted")),
                    privacy_status=PrivacyStatus(m.get("privacyStatus", "private_only")),
                )
            )

        interviews_data = self.sim_adapter.provider.simulated_interview_responses(
            household.household_id, [m.member_id for m in created_members]
        )
        for interview in interviews_data:
            session = PrivateInterviewSession(
                session_id=self.ctx.id_gen.next("session"),
                household_id=household.household_id,
                member_id=interview["memberId"],
                status=InterviewStatus.COMPLETED,
                transcript_reference=interview["transcriptReference"],
            )
            self.ctx.interviews.create(session)
            constraints = [
                DerivedConstraint(
                    constraint_id=self.ctx.id_gen.next("constraint"),
                    household_id=household.household_id,
                    member_id=interview["memberId"],
                    category=c["category"],
                    preference_or_requirement=c["preferenceOrRequirement"],
                    importance_weight=float(c["importanceWeight"]),
                    flexibility=float(c["flexibility"]),
                    privacy_classification=PrivacyClassification(c["privacyClassification"]),
                    source_session_reference=session.session_id,
                )
                for c in interview["derivedConstraints"]
            ]
            self.ctx.constraints.create_many(constraints)
            session.extracted_constraint_references = [c.constraint_id for c in constraints]
            self.ctx.interviews.update(session)

        shared_constraints = self.list_shareable_constraints(
            household.household_id, requester_member_id=created_members[0].member_id
        )
        agreement = self.generate_agreement_proposal(
            household.household_id,
            requester_member_id=created_members[0].member_id,
            derived_constraint_ids=[c.constraint_id for c in shared_constraints],
        )

        # Predictable sample records make the settle-up workflow demonstrable. One
        # expense benefits only two of the three members. Reset clears state first,
        # so repeating the reset produces the same record counts.
        now = utcnow()
        priya, rahul, aman = created_members
        self.create_expense(household.household_id, priya.member_id, priya.member_id, "Groceries", 2450.00, "groceries", now)
        self.create_expense(household.household_id, rahul.member_id, rahul.member_id, "Internet bill", 899.00, "utilities", now)
        self.create_expense(household.household_id, aman.member_id, aman.member_id, "Cleaning supplies (shared by two)", 375.50, "household", now, split_member_ids=[priya.member_id, aman.member_id])
        self.create_expense(household.household_id, priya.member_id, priya.member_id, "Electricity bill", 1320.75, "utilities", now, split_member_ids=[priya.member_id, rahul.member_id, aman.member_id], split_ratios={priya.member_id: 2, rahul.member_id: 1, aman.member_id: 1})

        timeline = self.sim_adapter.provider.simulate_14_day_timeline(
            household.household_id,
            [m.member_id for m in created_members],
            start_at=utcnow(),
        )
        for signal in timeline["monitoringSignals"]:
            self.ctx.monitoring.create(
                MonitoringSignal(
                    signal_id=self.ctx.id_gen.next("signal"),
                    assignment_reference=signal["assignmentReference"],
                    member_reference=signal["memberReference"],
                    expected_contribution=float(signal["expectedContribution"]),
                    observed_contribution=float(signal["observedContribution"]),
                    timestamp=datetime.fromisoformat(signal["timestamp"]),
                ),
                household.household_id,
            )

        return {
            "mode": "DEVELOPMENT/DEMO ONLY",
            "household": household,
            "members": created_members,
            "agreement": agreement,
            "assignments": agreement.proposal,
            "monitoringSignals": self.ctx.monitoring.list_by_household(household.household_id),
            "simulatedIntegrations": timeline["simulatedIntegrations"],
        }
