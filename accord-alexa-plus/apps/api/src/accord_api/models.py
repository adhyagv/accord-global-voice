"""Core Accord domain models and deterministic lifecycle state machines."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class ConsentStatus(str, Enum):
    PENDING = "pending"
    GRANTED = "granted"
    REVOKED = "revoked"


class PrivacyStatus(str, Enum):
    PRIVATE_ONLY = "private_only"
    DERIVED_SHAREABLE = "derived_shareable"


class PrivacyClassification(str, Enum):
    PRIVATE = "private"
    SHAREABLE_DERIVED = "shareable_derived"


class InterviewStatus(str, Enum):
    DRAFT = "draft"
    STARTED = "started"
    IN_PROGRESS = "in_progress"
    SUBMITTED = "submitted"
    COMPLETED = "completed"


class AgreementStatus(str, Enum):
    DRAFT = "draft"
    PROPOSED = "proposed"
    APPROVED = "approved"
    CHANGES_REQUESTED = "changes_requested"
    VETOED = "vetoed"
    ACTIVE = "active"
    SUPERSEDED = "superseded"
    CLOSED = "closed"


class AssignmentStatus(str, Enum):
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    MISSED = "missed"


class DriftSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class DriftStatus(str, Enum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"


class RenegotiationStatus(str, Enum):
    REQUESTED = "requested"
    INTERVIEWING = "interviewing"
    PROPOSED = "proposed"
    APPROVED = "approved"
    ACTIVE = "active"


_INTERVIEW_TRANSITIONS = {
    InterviewStatus.DRAFT: {InterviewStatus.STARTED, InterviewStatus.IN_PROGRESS},
    InterviewStatus.STARTED: {InterviewStatus.SUBMITTED},
    InterviewStatus.IN_PROGRESS: {InterviewStatus.SUBMITTED},
    InterviewStatus.SUBMITTED: {InterviewStatus.COMPLETED},
    InterviewStatus.COMPLETED: set(),
}

_AGREEMENT_TRANSITIONS = {
    AgreementStatus.DRAFT: {AgreementStatus.PROPOSED},
    AgreementStatus.PROPOSED: {
        AgreementStatus.APPROVED,
        AgreementStatus.CHANGES_REQUESTED,
        AgreementStatus.VETOED,
    },
    AgreementStatus.APPROVED: {AgreementStatus.ACTIVE},
    AgreementStatus.CHANGES_REQUESTED: {AgreementStatus.PROPOSED, AgreementStatus.VETOED},
    AgreementStatus.VETOED: {AgreementStatus.PROPOSED, AgreementStatus.CLOSED},
    AgreementStatus.ACTIVE: {AgreementStatus.SUPERSEDED, AgreementStatus.CLOSED},
    AgreementStatus.SUPERSEDED: set(),
    AgreementStatus.CLOSED: set(),
}

_RENEGOTIATION_TRANSITIONS = {
    RenegotiationStatus.REQUESTED: {RenegotiationStatus.INTERVIEWING},
    RenegotiationStatus.INTERVIEWING: {RenegotiationStatus.PROPOSED},
    RenegotiationStatus.PROPOSED: {RenegotiationStatus.APPROVED, RenegotiationStatus.ACTIVE},
    RenegotiationStatus.APPROVED: {RenegotiationStatus.ACTIVE},
    RenegotiationStatus.ACTIVE: set(),
}


@dataclass(slots=True)
class Member:
    member_id: str
    display_name: str
    role: str
    consent_status: ConsentStatus = ConsentStatus.PENDING
    privacy_status: PrivacyStatus = PrivacyStatus.PRIVATE_ONLY


@dataclass(slots=True)
class Household:
    household_id: str
    name: str
    members: list[Member] = field(default_factory=list)
    scenario_metadata: dict[str, Any] = field(default_factory=dict)

    def add_member(self, member: Member) -> None:
        if any(existing.member_id == member.member_id for existing in self.members):
            raise ValueError("member_already_exists")
        self.members.append(member)


@dataclass(slots=True)
class PrivateInterviewSession:
    session_id: str
    household_id: str
    member_id: str
    status: InterviewStatus = InterviewStatus.STARTED
    transcript_reference: str | None = None
    # Private, in-memory answers for the local demo. Never included in the
    # shared interview serializer.
    private_answers: dict[str, str] = field(default_factory=dict)
    extracted_constraint_references: list[str] = field(default_factory=list)

    def transition(self, next_status: InterviewStatus) -> None:
        allowed = _INTERVIEW_TRANSITIONS[self.status]
        if next_status not in allowed:
            raise ValueError("invalid_interview_transition")
        self.status = next_status

    def to_private_record(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "household_id": self.household_id,
            "member_id": self.member_id,
            "status": self.status.value,
            "transcript_reference": self.transcript_reference,
            "private_answers": dict(self.private_answers),
            "extracted_constraint_references": list(self.extracted_constraint_references),
        }

    def to_shared_summary(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "household_id": self.household_id,
            "member_id": self.member_id,
            "status": self.status.value,
            "extracted_constraint_references": list(self.extracted_constraint_references),
        }


@dataclass(slots=True)
class DerivedConstraint:
    constraint_id: str
    household_id: str
    member_id: str
    category: str
    preference_or_requirement: str
    importance_weight: float
    flexibility: float
    privacy_classification: PrivacyClassification
    source_session_reference: str


@dataclass(slots=True)
class Assignment:
    assignment_id: str
    member_id: str
    task: str
    frequency: str
    estimated_effort: float
    assigned_date: datetime
    status: AssignmentStatus = AssignmentStatus.SCHEDULED
    # Set when a member marks the task completed. None for unfinished and legacy tasks.
    completed_at: datetime | None = None


@dataclass(slots=True)
class Expense:
    expense_id: str
    household_id: str
    payer_member_id: str
    description: str
    amount: float
    category: str
    expense_date: datetime
    # Beneficiaries may be a subset of household members. Empty means all
    # current household members for compatibility with old persisted records.
    split_member_ids: list[str] = field(default_factory=list)
    # Optional positive integer weights per beneficiary (e.g. 2:1 split).
    split_ratios: dict[str, int] = field(default_factory=dict)


@dataclass(slots=True)
class MediationSession:
    session_id: str
    household_id: str
    topic: str
    # Only neutral restatements and reviewed options are persisted. Never raw statements.
    restatements: list[dict[str, Any]]
    options: list[dict[str, Any]]
    votes: dict[str, str] = field(default_factory=dict)
    status: str = "open"
    winning_option_id: str | None = None
    tie: bool = False
    tie_break_rule: str = "Tie is resolved by the earliest option shown to members."
    draft_agreement_id: str | None = None
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    closed_at: datetime | None = None


@dataclass(slots=True)
class Counteroffer:
    member_id: str
    message: str
    submitted_at: datetime


@dataclass(slots=True)
class AgreementVersion:
    agreement_id: str
    household_id: str
    version: int
    status: AgreementStatus
    proposal: list[Assignment]
    fairness_score: float
    rationale: str
    approvals: list[str] = field(default_factory=list)
    vetoes: list[str] = field(default_factory=list)
    counteroffers: list[Counteroffer] = field(default_factory=list)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def transition(self, next_status: AgreementStatus) -> None:
        allowed = _AGREEMENT_TRANSITIONS[self.status]
        if next_status not in allowed:
            raise ValueError("invalid_agreement_transition")
        self.status = next_status

    def register_approval(self, member_id: str) -> None:
        if member_id not in self.approvals:
            self.approvals.append(member_id)

    def register_veto(self, member_id: str) -> None:
        if member_id not in self.vetoes:
            self.vetoes.append(member_id)

    def register_counteroffer(self, counteroffer: Counteroffer) -> None:
        self.counteroffers.append(counteroffer)


@dataclass(slots=True)
class MonitoringSignal:
    signal_id: str
    assignment_reference: str
    member_reference: str
    expected_contribution: float
    observed_contribution: float
    timestamp: datetime


@dataclass(slots=True)
class DriftReport:
    drift_id: str
    agreement_version_reference: str
    affected_members: list[str]
    detected_signals: list[str]
    severity: DriftSeverity
    explanation: str
    recommended_action: str
    evidence: list[str] = field(default_factory=list)
    affected_assignments: list[str] = field(default_factory=list)
    status: DriftStatus = DriftStatus.OPEN


@dataclass(slots=True)
class RenegotiationCycle:
    renegotiation_id: str
    household_id: str
    drift_id: str
    status: RenegotiationStatus = RenegotiationStatus.REQUESTED

    def transition(self, next_status: RenegotiationStatus) -> None:
        allowed = _RENEGOTIATION_TRANSITIONS[self.status]
        if next_status not in allowed:
            raise ValueError("invalid_renegotiation_transition")
        self.status = next_status
