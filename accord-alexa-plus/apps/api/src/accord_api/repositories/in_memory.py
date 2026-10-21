"""In-memory repository implementations for TASK 003."""

from __future__ import annotations

from collections import defaultdict

from ..models import (
    AgreementVersion,
    Assignment,
    DerivedConstraint,
    DriftReport,
    Expense,
    Household,
    Member,
    MonitoringSignal,
    PrivateInterviewSession,
    RenegotiationCycle,
)


class InMemoryHouseholdRepository:
    def __init__(self) -> None:
        self._items: dict[str, Household] = {}

    def create(self, household: Household) -> Household:
        self._items[household.household_id] = household
        return household

    def get(self, household_id: str) -> Household | None:
        return self._items.get(household_id)

    def list(self) -> list[Household]:
        return list(self._items.values())

    def clear(self) -> None:
        self._items.clear()


class InMemoryMemberRepository:
    def __init__(self) -> None:
        self._items: dict[str, Member] = {}
        self._by_household: dict[str, list[str]] = defaultdict(list)

    def add(self, household_id: str, member: Member) -> Member:
        self._items[member.member_id] = member
        self._by_household[household_id].append(member.member_id)
        return member

    def get(self, member_id: str) -> Member | None:
        return self._items.get(member_id)

    def list_by_household(self, household_id: str) -> list[Member]:
        return [self._items[mid] for mid in self._by_household.get(household_id, [])]

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()


class InMemoryInterviewRepository:
    def __init__(self) -> None:
        self._items: dict[str, PrivateInterviewSession] = {}
        self._by_household: dict[str, list[str]] = defaultdict(list)
        self._by_member: dict[str, list[str]] = defaultdict(list)

    def create(self, session: PrivateInterviewSession) -> PrivateInterviewSession:
        self._items[session.session_id] = session
        self._by_household[session.household_id].append(session.session_id)
        self._by_member[session.member_id].append(session.session_id)
        return session

    def get(self, session_id: str) -> PrivateInterviewSession | None:
        return self._items.get(session_id)

    def list_by_household(self, household_id: str) -> list[PrivateInterviewSession]:
        return [self._items[sid] for sid in self._by_household.get(household_id, [])]

    def list_by_member(self, member_id: str) -> list[PrivateInterviewSession]:
        return [self._items[sid] for sid in self._by_member.get(member_id, [])]

    def update(self, session: PrivateInterviewSession) -> PrivateInterviewSession:
        self._items[session.session_id] = session
        return session

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()
        self._by_member.clear()


class InMemoryConstraintRepository:
    def __init__(self) -> None:
        self._items: dict[str, DerivedConstraint] = {}
        self._by_member: dict[str, list[str]] = defaultdict(list)
        self._by_household: dict[str, list[str]] = defaultdict(list)

    def create_many(self, constraints: list[DerivedConstraint]) -> list[DerivedConstraint]:
        for constraint in constraints:
            self._items[constraint.constraint_id] = constraint
            member_ids = self._by_member[constraint.member_id]
            if constraint.constraint_id not in member_ids:
                member_ids.append(constraint.constraint_id)
            household_ids = self._by_household[constraint.household_id]
            if constraint.constraint_id not in household_ids:
                household_ids.append(constraint.constraint_id)
        return constraints

    def list_by_member(self, member_id: str) -> list[DerivedConstraint]:
        return [self._items[cid] for cid in self._by_member.get(member_id, [])]

    def list_shareable_by_household(self, household_id: str) -> list[DerivedConstraint]:
        return [self._items[cid] for cid in self._by_household.get(household_id, [])]

    def list_by_ids(self, constraint_ids: list[str]) -> list[DerivedConstraint]:
        return [self._items[cid] for cid in constraint_ids if cid in self._items]

    def clear(self) -> None:
        self._items.clear()
        self._by_member.clear()
        self._by_household.clear()


class InMemoryAgreementRepository:
    def __init__(self) -> None:
        self._items: dict[tuple[str, int], AgreementVersion] = {}
        self._by_household: dict[str, list[tuple[str, int]]] = defaultdict(list)
        self._by_agreement: dict[str, list[int]] = defaultdict(list)

    def create(self, agreement: AgreementVersion) -> AgreementVersion:
        key = (agreement.agreement_id, agreement.version)
        self._items[key] = agreement
        self._by_household[agreement.household_id].append(key)
        self._by_agreement[agreement.agreement_id].append(agreement.version)
        self._by_agreement[agreement.agreement_id].sort()
        return agreement

    def get(self, agreement_id: str, version: int) -> AgreementVersion | None:
        return self._items.get((agreement_id, version))

    def list_versions(self, agreement_id: str) -> list[AgreementVersion]:
        return [self._items[(agreement_id, v)] for v in self._by_agreement.get(agreement_id, [])]

    def list_by_household(self, household_id: str) -> list[AgreementVersion]:
        return [self._items[key] for key in self._by_household.get(household_id, [])]

    def latest_by_household(self, household_id: str) -> AgreementVersion | None:
        entries = self._by_household.get(household_id, [])
        if not entries:
            return None
        return self._items[entries[-1]]

    def update(self, agreement: AgreementVersion) -> AgreementVersion:
        self._items[(agreement.agreement_id, agreement.version)] = agreement
        return agreement

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()
        self._by_agreement.clear()


class InMemoryAssignmentRepository:
    def __init__(self) -> None:
        self._items: dict[str, Assignment] = {}
        self._household_index: dict[str, list[str]] = defaultdict(list)
        self._member_index: dict[str, list[str]] = defaultdict(list)
        self._agreement_index: dict[tuple[str, int], list[str]] = defaultdict(list)

    def create(self, assignment: Assignment) -> Assignment:
        self._items[assignment.assignment_id] = assignment
        return assignment

    def create_many(self, assignments: list[Assignment]) -> list[Assignment]:
        for assignment in assignments:
            self._items[assignment.assignment_id] = assignment
        return assignments

    def link_to_household(self, household_id: str, assignment_ids: list[str]) -> None:
        # Idempotent links prevent duplicate task rows after reset/replay or retries.
        known = set(self._household_index[household_id])
        for assignment_id in assignment_ids:
            if assignment_id not in self._items or assignment_id in known:
                continue
            self._household_index[household_id].append(assignment_id)
            known.add(assignment_id)
            assignment = self._items[assignment_id]
            if assignment_id not in self._member_index[assignment.member_id]:
                self._member_index[assignment.member_id].append(assignment_id)

    def link_to_agreement(self, agreement_id: str, version: int, assignment_ids: list[str]) -> None:
        key = (agreement_id, version)
        known = set(self._agreement_index[key])
        for assignment_id in assignment_ids:
            if assignment_id in self._items and assignment_id not in known:
                self._agreement_index[key].append(assignment_id)
                known.add(assignment_id)

    def get(self, assignment_id: str) -> Assignment | None:
        return self._items.get(assignment_id)

    def list_by_household(self, household_id: str) -> list[Assignment]:
        # De-duplicate legacy persisted indexes while preserving stable order.
        ids = dict.fromkeys(self._household_index.get(household_id, []))
        return [self._items[aid] for aid in ids if aid in self._items]

    def list_by_member(self, member_id: str) -> list[Assignment]:
        return [self._items[aid] for aid in self._member_index.get(member_id, [])]

    def list_by_agreement(self, agreement_id: str, version: int) -> list[Assignment]:
        return [self._items[aid] for aid in self._agreement_index.get((agreement_id, version), [])]

    def update(self, assignment: Assignment) -> Assignment:
        self._items[assignment.assignment_id] = assignment
        return assignment

    def reassign(self, assignment: Assignment, member_id: str) -> Assignment:
        """Update member indexes atomically for an explicit assignment change."""
        previous_member_id = assignment.member_id
        ids = self._member_index.get(previous_member_id, [])
        self._member_index[previous_member_id] = [aid for aid in ids if aid != assignment.assignment_id]
        assignment.member_id = member_id
        self._items[assignment.assignment_id] = assignment
        if assignment.assignment_id not in self._member_index[member_id]:
            self._member_index[member_id].append(assignment.assignment_id)
        return assignment

    def clear(self) -> None:
        self._items.clear()
        self._household_index.clear()
        self._member_index.clear()
        self._agreement_index.clear()


class InMemoryExpenseRepository:
    def __init__(self) -> None:
        self._items: dict[str, Expense] = {}
        self._by_household: dict[str, list[str]] = defaultdict(list)

    def create(self, expense: Expense) -> Expense:
        self._items[expense.expense_id] = expense
        self._by_household[expense.household_id].append(expense.expense_id)
        return expense

    def list_by_household(self, household_id: str) -> list[Expense]:
        return [self._items[eid] for eid in self._by_household.get(household_id, [])]

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()


class InMemoryMonitoringRepository:
    def __init__(self) -> None:
        self._items: dict[str, MonitoringSignal] = {}
        self._by_household: dict[str, list[str]] = defaultdict(list)
        self._by_member: dict[str, list[str]] = defaultdict(list)

    def create(self, signal: MonitoringSignal, household_id: str) -> MonitoringSignal:
        self._items[signal.signal_id] = signal
        self._by_household[household_id].append(signal.signal_id)
        self._by_member[signal.member_reference].append(signal.signal_id)
        return signal

    def list_by_household(self, household_id: str) -> list[MonitoringSignal]:
        return [self._items[sid] for sid in self._by_household.get(household_id, [])]

    def list_by_member(self, member_id: str) -> list[MonitoringSignal]:
        return [self._items[sid] for sid in self._by_member.get(member_id, [])]

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()
        self._by_member.clear()


class InMemoryDriftRepository:
    def __init__(self) -> None:
        self._items: dict[str, DriftReport] = {}
        self._by_household: dict[str, list[str]] = defaultdict(list)

    def create(self, report: DriftReport, household_id: str) -> DriftReport:
        self._items[report.drift_id] = report
        self._by_household[household_id].append(report.drift_id)
        return report

    def get(self, drift_id: str) -> DriftReport | None:
        return self._items.get(drift_id)

    def list_by_household(self, household_id: str) -> list[DriftReport]:
        return [self._items[rid] for rid in self._by_household.get(household_id, [])]

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()


class InMemoryRenegotiationRepository:
    def __init__(self) -> None:
        self._items: dict[str, RenegotiationCycle] = {}
        self._by_household: dict[str, list[str]] = defaultdict(list)

    def create(self, cycle: RenegotiationCycle) -> RenegotiationCycle:
        self._items[cycle.renegotiation_id] = cycle
        self._by_household[cycle.household_id].append(cycle.renegotiation_id)
        return cycle

    def get(self, renegotiation_id: str) -> RenegotiationCycle | None:
        return self._items.get(renegotiation_id)

    def update(self, cycle: RenegotiationCycle) -> RenegotiationCycle:
        self._items[cycle.renegotiation_id] = cycle
        return cycle

    def list_by_household(self, household_id: str) -> list[RenegotiationCycle]:
        return [self._items[rid] for rid in self._by_household.get(household_id, [])]

    def clear(self) -> None:
        self._items.clear()
        self._by_household.clear()
