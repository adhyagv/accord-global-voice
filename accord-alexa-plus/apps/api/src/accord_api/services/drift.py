"""Deterministic drift detection service."""

from __future__ import annotations

from ..models import DriftSeverity, MonitoringSignal


class DriftDetectionService:
    def evaluate(self, signals: list[MonitoringSignal]) -> tuple[DriftSeverity, list[str], list[str], str]:
        if not signals:
            return (
                DriftSeverity.LOW,
                [],
                ["No monitoring signals available."],
                "Collect additional monitoring data.",
            )

        total_expected = 0.0
        total_observed = 0.0
        evidence: list[str] = []
        affected_members: set[str] = set()

        for signal in signals:
            total_expected += signal.expected_contribution
            total_observed += signal.observed_contribution
            deviation = signal.expected_contribution - signal.observed_contribution
            if deviation > 0.0:
                affected_members.add(signal.member_reference)
                evidence.append(
                    f"signal={signal.signal_id} member={signal.member_reference} deviation={deviation:.2f}"
                )

        if total_expected <= 0:
            ratio = 0.0
        else:
            ratio = (total_expected - total_observed) / total_expected

        if ratio >= 0.3:
            severity = DriftSeverity.HIGH
            action = "Start renegotiation interview cycle immediately."
        elif ratio >= 0.15:
            severity = DriftSeverity.MEDIUM
            action = "Prompt members for adjustment and monitor next 7 days."
        else:
            severity = DriftSeverity.LOW
            action = "Maintain agreement and continue routine monitoring."

        return severity, sorted(affected_members), evidence, action
