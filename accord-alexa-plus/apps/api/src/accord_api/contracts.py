"""Request/response contract types for Accord API endpoints."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from .models import (
    AgreementVersion,
    DerivedConstraint,
    DriftReport,
    Household,
    Member,
    MonitoringSignal,
    PrivateInterviewSession,
)


@dataclass(slots=True)
class CreateHouseholdRequest:
    name: str
    scenario_metadata: dict[str, str] = field(default_factory=dict)


@dataclass(slots=True)
class CreateHouseholdResponse:
    household: Household


@dataclass(slots=True)
class AddMemberRequest:
    household_id: str
    member: Member


@dataclass(slots=True)
class AddMemberResponse:
    household: Household


@dataclass(slots=True)
class StartPrivateInterviewRequest:
    household_id: str
    member_id: str


@dataclass(slots=True)
class StartPrivateInterviewResponse:
    interview_session: PrivateInterviewSession


@dataclass(slots=True)
class SubmitInterviewRequest:
    session_id: str
    transcript_reference: str


@dataclass(slots=True)
class SubmitInterviewResponse:
    interview_session: PrivateInterviewSession


@dataclass(slots=True)
class DeriveConstraintsRequest:
    session_id: str


@dataclass(slots=True)
class DeriveConstraintsResponse:
    constraints: list[DerivedConstraint]


@dataclass(slots=True)
class GenerateAgreementProposalRequest:
    household_id: str
    derived_constraint_ids: list[str]


@dataclass(slots=True)
class GenerateAgreementProposalResponse:
    agreement: AgreementVersion


@dataclass(slots=True)
class ApproveProposalRequest:
    agreement_id: str
    version: int
    member_id: str


@dataclass(slots=True)
class VetoProposalRequest:
    agreement_id: str
    version: int
    member_id: str
    reason: str


@dataclass(slots=True)
class CounterProposalRequest:
    agreement_id: str
    version: int
    member_id: str
    proposal_delta_summary: str


@dataclass(slots=True)
class AgreementActionResponse:
    agreement: AgreementVersion


@dataclass(slots=True)
class ActivateAgreementRequest:
    agreement_id: str
    version: int


@dataclass(slots=True)
class ActivateAgreementResponse:
    agreement: AgreementVersion


@dataclass(slots=True)
class RecordMonitoringSignalRequest:
    signal: MonitoringSignal


@dataclass(slots=True)
class RecordMonitoringSignalResponse:
    signal_id: str
    recorded_at: datetime


@dataclass(slots=True)
class GenerateDriftReportRequest:
    agreement_id: str
    version: int


@dataclass(slots=True)
class GenerateDriftReportResponse:
    drift_report: DriftReport


@dataclass(slots=True)
class StartRenegotiationRequest:
    household_id: str
    drift_id: str


@dataclass(slots=True)
class StartRenegotiationResponse:
    interview_sessions: list[PrivateInterviewSession]
