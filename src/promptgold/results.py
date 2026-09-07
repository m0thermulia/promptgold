"""Run results collector: one data model feeding terminal + HTML renderers.

The plugin appends a PromptTestResult per prompt test; renderers read them.
No pytest imports here — this module is UI-agnostic.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field


@dataclass
class VerdictResult:
    criterion: str
    expected: bool | None  # None = no golden to compare
    actual: bool
    reason: str = ""

    @property
    def regressed(self) -> bool:
        return self.expected is not None and self.expected != self.actual


@dataclass
class PromptTestResult:
    nodeid: str
    model: str
    verdicts: list[VerdictResult] = field(default_factory=list)
    cost_usd: float | None = None
    latency_ms: float = 0.0
    cassette: str = "live"  # "live" | "recorded" | "replayed"
    error: str | None = None

    @property
    def name(self) -> str:
        return self.nodeid.split("::")[-1]

    @property
    def passed(self) -> bool:
        return self.error is None and not any(v.regressed for v in self.verdicts)


@dataclass
class RunResults:
    tests: list[PromptTestResult] = field(default_factory=list)
    started_at: float = field(default_factory=time.time)

    @property
    def passed(self) -> int:
        return sum(1 for t in self.tests if t.passed)

    @property
    def failed(self) -> int:
        return sum(1 for t in self.tests if not t.passed)

    @property
    def total_cost(self) -> float | None:
        costs = [t.cost_usd for t in self.tests if t.cost_usd is not None]
        return sum(costs) if costs else None

    @property
    def recorded(self) -> int:
        return sum(1 for t in self.tests if t.cassette == "recorded")

    @property
    def replayed(self) -> int:
        return sum(1 for t in self.tests if t.cassette == "replayed")
