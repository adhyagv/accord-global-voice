"""Utilities for deterministic IDs and time."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass(slots=True)
class CounterIdGenerator:
    prefix_counters: dict[str, int] = field(default_factory=dict)

    def next(self, prefix: str) -> str:
        value = self.prefix_counters.get(prefix, 0) + 1
        self.prefix_counters[prefix] = value
        return f"{prefix}-{value}"


def utcnow() -> datetime:
    return datetime.now(UTC)
