"""Application service context and dependency container."""

from __future__ import annotations

from dataclasses import dataclass, field
import os
from pathlib import Path

from ..repositories.in_memory import (
    InMemoryAgreementRepository,
    InMemoryAssignmentRepository,
    InMemoryConstraintRepository,
    InMemoryDriftRepository,
    InMemoryExpenseRepository,
    InMemoryHouseholdRepository,
    InMemoryInterviewRepository,
    InMemoryMemberRepository,
    InMemoryMonitoringRepository,
    InMemoryRenegotiationRepository,
)
from ..utils import CounterIdGenerator
from ..models import MediationSession
from ..persistence import SQLiteSnapshotStore
from .drift import DriftDetectionService
from .fairness import DeterministicWorkloadFairnessSolver


@dataclass(slots=True)
class AppContext:
    households: InMemoryHouseholdRepository
    members: InMemoryMemberRepository
    interviews: InMemoryInterviewRepository
    constraints: InMemoryConstraintRepository
    agreements: InMemoryAgreementRepository
    assignments: InMemoryAssignmentRepository
    expenses: InMemoryExpenseRepository
    monitoring: InMemoryMonitoringRepository
    drift_reports: InMemoryDriftRepository
    renegotiations: InMemoryRenegotiationRepository
    id_gen: CounterIdGenerator
    fairness_solver: DeterministicWorkloadFairnessSolver
    drift_service: DriftDetectionService
    mediation_sessions: dict[str, MediationSession] = field(default_factory=dict)
    snapshot_store: SQLiteSnapshotStore | None = None

    def persist(self) -> None:
        if self.snapshot_store is not None:
            self.snapshot_store.save(self)

    def reset(self) -> None:
        self.households.clear()
        self.members.clear()
        self.interviews.clear()
        self.constraints.clear()
        self.agreements.clear()
        self.assignments.clear()
        self.expenses.clear()
        self.monitoring.clear()
        self.drift_reports.clear()
        self.renegotiations.clear()
        self.mediation_sessions.clear()
        self.id_gen.prefix_counters.clear()


def build_context(*, persistence: bool | None = None, database_path: str | Path | None = None) -> AppContext:
    """Build the app context, enabling SQLite persistence by default.

    Set ACCORD_PERSISTENCE=memory to use ephemeral storage, or ACCORD_DB_PATH to
    choose a SQLite file location.
    """
    if persistence is None:
        persistence = os.environ.get("ACCORD_PERSISTENCE", "sqlite").casefold() != "memory"

    context = AppContext(
        households=InMemoryHouseholdRepository(),
        members=InMemoryMemberRepository(),
        interviews=InMemoryInterviewRepository(),
        constraints=InMemoryConstraintRepository(),
        agreements=InMemoryAgreementRepository(),
        assignments=InMemoryAssignmentRepository(),
        expenses=InMemoryExpenseRepository(),
        monitoring=InMemoryMonitoringRepository(),
        drift_reports=InMemoryDriftRepository(),
        renegotiations=InMemoryRenegotiationRepository(),
        id_gen=CounterIdGenerator(),
        fairness_solver=DeterministicWorkloadFairnessSolver(),
        drift_service=DriftDetectionService(),
    )
    if persistence:
        store = SQLiteSnapshotStore(database_path or SQLiteSnapshotStore.default_path())
        context.snapshot_store = store
        store.load(context)
    return context
