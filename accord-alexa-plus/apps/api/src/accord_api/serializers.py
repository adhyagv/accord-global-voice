"""Serialization helpers with private/shared response separation."""

from __future__ import annotations

from .models import (
    AgreementVersion,
    Assignment,
    DerivedConstraint,
    DriftReport,
    Expense,
    Household,
    Member,
    MonitoringSignal,
    PrivateInterviewSession,
    PrivacyClassification,
    RenegotiationCycle,
)


def serialize_member(member: Member) -> dict:
    return {
        "memberId": member.member_id,
        "displayName": member.display_name,
        "role": member.role,
        "consentStatus": member.consent_status.value,
        "privacyStatus": member.privacy_status.value,
    }


def serialize_household(household: Household) -> dict:
    return {
        "householdId": household.household_id,
        "name": household.name,
        "members": [serialize_member(m) for m in household.members],
        "scenarioMetadata": dict(household.scenario_metadata),
    }


def serialize_interview_shared(session: PrivateInterviewSession) -> dict:
    return {
        "sessionId": session.session_id,
        "householdId": session.household_id,
        "memberId": session.member_id,
        "status": session.status.value,
        "extractedConstraintReferences": list(session.extracted_constraint_references),
    }


def serialize_interview_private(session: PrivateInterviewSession) -> dict:
    payload = serialize_interview_shared(session)
    payload["transcriptReference"] = session.transcript_reference
    payload["privateAnswers"] = dict(session.private_answers)
    return payload


def serialize_constraint(constraint: DerivedConstraint) -> dict:
    return {
        "constraintId": constraint.constraint_id,
        "householdId": constraint.household_id,
        "memberId": constraint.member_id,
        "category": constraint.category,
        "preferenceOrRequirement": constraint.preference_or_requirement,
        "importanceWeight": constraint.importance_weight,
        "flexibility": constraint.flexibility,
        "privacyClassification": constraint.privacy_classification.value,
        "sourceSessionReference": constraint.source_session_reference,
    }


def serialize_constraint_shared(constraint: DerivedConstraint) -> dict:
    payload = serialize_constraint(constraint)
    if constraint.privacy_classification == PrivacyClassification.PRIVATE:
        payload["preferenceOrRequirement"] = "private"
        payload["sourceSessionReference"] = "private"
    return payload


def serialize_assignment(assignment: Assignment) -> dict:
    return {
        "assignmentId": assignment.assignment_id,
        "memberId": assignment.member_id,
        "task": assignment.task,
        "frequency": assignment.frequency,
        "estimatedEffort": assignment.estimated_effort,
        "assignedDate": assignment.assigned_date.isoformat(),
        "completedAt": assignment.completed_at.isoformat() if assignment.completed_at else None,
        "status": assignment.status.value,
    }


def serialize_expense(expense: Expense) -> dict:
    return {
        "expenseId": expense.expense_id,
        "householdId": expense.household_id,
        "payerMemberId": expense.payer_member_id,
        "description": expense.description,
        "amount": expense.amount,
        "category": expense.category,
        "expenseDate": expense.expense_date.isoformat(),
        "splitMemberIds": list(expense.split_member_ids),
        "splitRatios": dict(expense.split_ratios),
    }


def serialize_agreement(agreement: AgreementVersion) -> dict:
    return {
        "agreementId": agreement.agreement_id,
        "householdId": agreement.household_id,
        "version": agreement.version,
        "status": agreement.status.value,
        "proposal": [serialize_assignment(a) for a in agreement.proposal],
        "fairnessScore": agreement.fairness_score,
        "rationale": agreement.rationale,
        "approvals": list(agreement.approvals),
        "vetoes": list(agreement.vetoes),
        "counteroffers": [
            {
                "memberId": c.member_id,
                "message": c.message,
                "submittedAt": c.submitted_at.isoformat(),
            }
            for c in agreement.counteroffers
        ],
        "createdAt": agreement.created_at.isoformat(),
    }


def serialize_signal(signal: MonitoringSignal) -> dict:
    return {
        "signalId": signal.signal_id,
        "assignmentReference": signal.assignment_reference,
        "memberReference": signal.member_reference,
        "expectedContribution": signal.expected_contribution,
        "observedContribution": signal.observed_contribution,
        "timestamp": signal.timestamp.isoformat(),
    }


def serialize_drift(report: DriftReport) -> dict:
    return {
        "driftId": report.drift_id,
        "agreementVersionReference": report.agreement_version_reference,
        "affectedMembers": list(report.affected_members),
        "affectedAssignments": list(report.affected_assignments),
        "detectedSignals": list(report.detected_signals),
        "severity": report.severity.value,
        "explanation": report.explanation,
        "evidence": list(report.evidence),
        "recommendedAction": report.recommended_action,
        "status": report.status.value,
    }


def serialize_renegotiation(cycle: RenegotiationCycle) -> dict:
    return {
        "renegotiationId": cycle.renegotiation_id,
        "householdId": cycle.household_id,
        "driftId": cycle.drift_id,
        "status": cycle.status.value,
    }
