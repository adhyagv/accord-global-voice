"""Adapter for deterministic simulated scenario generation."""

from __future__ import annotations

import sys
from pathlib import Path

_SIM_SRC = Path(__file__).resolve().parents[5] / "packages" / "sim" / "src"
if str(_SIM_SRC) not in sys.path:
    sys.path.append(str(_SIM_SRC))

from accord_sim.generator import DefaultSimulationProvider  # type: ignore  # noqa: E402


class SimulationAdapter:
    def __init__(self) -> None:
        self.provider = DefaultSimulationProvider(seed=7)
