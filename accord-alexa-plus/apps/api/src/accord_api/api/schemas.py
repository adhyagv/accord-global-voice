"""FastAPI request/response schemas."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class CreateHouseholdRequest(BaseModel):
    name: str
    scenarioMetadata: dict[str, Any] = Field(default_factory=dict)


class AddMemberRequest(BaseModel):
    displayName: str
    role: str


class UpdateMemberConsentRequest(BaseModel):
    consentStatus: Literal["pending", "granted", "revoked"]


class StartInterviewRequest(BaseModel):
    householdId: str
    memberId: str


class SubmitInterviewRequest(BaseModel):
    transcriptReference: str
    answers: dict[str, str] = Field(default_factory=dict)


class MemberActionRequest(BaseModel):
    memberId: str


class CounterRequest(BaseModel):
    memberId: str
    proposalDeltaSummary: str


class GenerateAgreementRequest(BaseModel):
    householdId: str
    derivedConstraintIds: list[str]


class CreateAssignmentRequest(BaseModel):
    householdId: str
    memberId: str
    task: str
    frequency: str
    estimatedEffort: float
    assignedDate: datetime


class UpdateAssignmentStatusRequest(BaseModel):
    status: Literal["scheduled", "in_progress", "completed", "missed"]


class ReassignAssignmentRequest(BaseModel):
    memberId: str = Field(min_length=1, max_length=100)


class WeeklyMealPlanRequest(BaseModel):
    householdId: str = Field(min_length=1, max_length=100)
    days: int = Field(default=7, ge=7, le=7)


class CreateExpenseRequest(BaseModel):
    householdId: str
    payerMemberId: str
    description: str = Field(min_length=1, max_length=160)
    amount: float = Field(gt=0, le=1_000_000)
    category: str = Field(default="shared", min_length=1, max_length=60)
    expenseDate: datetime
    # Omit these fields for a classic equal split across the whole household.
    splitMemberIds: list[str] | None = Field(default=None, max_length=50)
    splitRatios: dict[str, int] | None = Field(default=None, max_length=50)


class RecordMonitoringSignalRequest(BaseModel):
    householdId: str
    assignmentReference: str
    memberReference: str
    expectedContribution: float
    observedContribution: float
    timestamp: datetime


class GenerateDriftReportRequest(BaseModel):
    agreementId: str
    version: int


class StartRenegotiationRequest(BaseModel):
    householdId: str
    driftId: str


class FairnessTaskInput(BaseModel):
    task: str = Field(min_length=1, max_length=120)
    estimatedEffort: float = Field(gt=0, le=600)


class FairnessCompareRequest(BaseModel):
    householdId: str = Field(min_length=1, max_length=100)
    preferenceWeight: float = Field(default=0.5, ge=0, le=1)
    tasks: list[FairnessTaskInput] = Field(
        default_factory=lambda: [
            FairnessTaskInput(task="Dishes", estimatedEffort=30),
            FairnessTaskInput(task="Trash and recycling", estimatedEffort=15),
            FairnessTaskInput(task="Bathroom cleaning", estimatedEffort=40),
            FairnessTaskInput(task="Kitchen floor", estimatedEffort=25),
            FairnessTaskInput(task="Laundry", estimatedEffort=35),
        ],
        min_length=1,
        max_length=25,
    )


class MediationPerspectiveInput(BaseModel):
    memberId: str = Field(min_length=1, max_length=100)
    statement: str = Field(min_length=1, max_length=1600)
    consentToShare: bool

    @field_validator("statement")
    @classmethod
    def trim_statement(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("statement must not be blank")
        return value


class MediationRequest(BaseModel):
    householdId: str = Field(min_length=1, max_length=100)
    perspectives: list[MediationPerspectiveInput] = Field(min_length=2, max_length=6)

    @model_validator(mode="after")
    def unique_members_and_consented_sharing(self):
        ids = [perspective.memberId for perspective in self.perspectives]
        if len(ids) != len(set(ids)):
            raise ValueError("Each member can provide only one perspective per mediation.")
        if any(not perspective.consentToShare for perspective in self.perspectives):
            raise ValueError("Every perspective must include explicit consent to share it for mediation.")
        return self


class DraftAgreementClausesRequest(BaseModel):
    householdId: str = Field(min_length=1, max_length=100)
    derivedConstraintIds: list[str] = Field(default_factory=list, max_length=100)


class MediationSessionRestatement(BaseModel):
    memberId: str = Field(min_length=1, max_length=100)
    label: str = Field(default="Member", max_length=60)
    needsRestatement: str = Field(min_length=1, max_length=600)
    privateDetailsOmitted: bool = True


class MediationSessionOption(BaseModel):
    id: str = Field(min_length=1, max_length=100)
    title: str = Field(min_length=1, max_length=120)
    proposal: str = Field(min_length=1, max_length=900)
    tradeOff: str = Field(min_length=1, max_length=700)
    requiresHouseholdConfirmation: bool = True


class CreateMediationSessionRequest(BaseModel):
    householdId: str = Field(min_length=1, max_length=100)
    topic: str = Field(min_length=1, max_length=160)
    restatements: list[MediationSessionRestatement] = Field(min_length=2, max_length=6)
    options: list[MediationSessionOption] = Field(min_length=3, max_length=3)

    @model_validator(mode="after")
    def validate_safe_session_content(self):
        member_ids = [row.memberId for row in self.restatements]
        option_ids = [option.id for option in self.options]
        if len(set(member_ids)) != len(member_ids):
            raise ValueError("Restatements must have unique member IDs.")
        if len(set(option_ids)) != len(option_ids):
            raise ValueError("Mediation options must have unique IDs.")
        return self


class CastMediationVoteRequest(BaseModel):
    optionId: str = Field(min_length=1, max_length=100)


class FairnessSimulationRequest(BaseModel):
    householdId: str = Field(min_length=1, max_length=100)
    seed: int = Field(default=7, ge=0, le=2_147_483_647)
    weeks: int = Field(default=8, ge=8, le=8)
    preferenceWeight: float = Field(default=0.5, ge=0, le=1)
    tasks: list[FairnessTaskInput] = Field(
        default_factory=lambda: [
            FairnessTaskInput(task="Dishes", estimatedEffort=30),
            FairnessTaskInput(task="Trash and recycling", estimatedEffort=15),
            FairnessTaskInput(task="Bathroom cleaning", estimatedEffort=45),
            FairnessTaskInput(task="Kitchen floor", estimatedEffort=25),
            FairnessTaskInput(task="Laundry", estimatedEffort=35),
            FairnessTaskInput(task="Meal prep", estimatedEffort=40),
        ],
        min_length=1,
        max_length=30,
    )
