from __future__ import annotations

import sys
from datetime import UTC, datetime
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "api" / "src"))

from accord_api.models import (  # noqa: E402
    AgreementStatus,
    AgreementVersion,
    Assignment,
    Counteroffer,
    InterviewStatus,
    PrivateInterviewSession,
)


class TestPrivacyIsolation(unittest.TestCase):
    def test_private_interview_shared_summary_omits_transcript_reference(self) -> None:
        session = PrivateInterviewSession(
            session_id="s1",
            household_id="h1",
            member_id="m1",
            status=InterviewStatus.SUBMITTED,
            transcript_reference="private://h1/m1/session",
            extracted_constraint_references=["c1"],
        )

        shared = session.to_shared_summary()
        self.assertNotIn("transcript_reference", shared)
        self.assertEqual(shared["member_id"], "m1")


class TestAgreementVersioning(unittest.TestCase):
    def test_register_actions_and_preserve_version(self) -> None:
        assignment = Assignment(
            assignment_id="a1",
            member_id="m1",
            task="dishes",
            frequency="weekly",
            estimated_effort=30.0,
            assigned_date=datetime.now(UTC),
            status="scheduled",
        )
        agreement = AgreementVersion(
            agreement_id="ag-1",
            household_id="h1",
            version=1,
            status=AgreementStatus.PROPOSED,
            proposal=[assignment],
            fairness_score=0.85,
            rationale="balanced effort",
        )

        agreement.register_approval("m1")
        agreement.register_veto("m2")
        agreement.register_counteroffer(
            Counteroffer(
                member_id="m3",
                message="swap trash and dishes",
                submitted_at=datetime.now(UTC),
            )
        )

        self.assertEqual(agreement.version, 1)
        self.assertEqual(agreement.approvals, ["m1"])
        self.assertEqual(agreement.vetoes, ["m2"])
        self.assertEqual(len(agreement.counteroffers), 1)


class TestStateTransitions(unittest.TestCase):
    def test_interview_valid_transitions(self) -> None:
        session = PrivateInterviewSession(
            session_id="s1", household_id="h1", member_id="m1", status=InterviewStatus.DRAFT
        )
        session.transition(InterviewStatus.IN_PROGRESS)
        session.transition(InterviewStatus.SUBMITTED)
        session.transition(InterviewStatus.COMPLETED)
        self.assertEqual(session.status, InterviewStatus.COMPLETED)

    def test_interview_invalid_transition_raises(self) -> None:
        session = PrivateInterviewSession(
            session_id="s1", household_id="h1", member_id="m1", status=InterviewStatus.DRAFT
        )
        with self.assertRaises(ValueError):
            session.transition(InterviewStatus.COMPLETED)

    def test_agreement_invalid_transition_raises(self) -> None:
        agreement = AgreementVersion(
            agreement_id="ag-1",
            household_id="h1",
            version=1,
            status=AgreementStatus.ACTIVE,
            proposal=[],
            fairness_score=0.9,
            rationale="ok",
        )
        with self.assertRaises(ValueError):
            agreement.transition(AgreementStatus.PROPOSED)


if __name__ == "__main__":
    unittest.main()
