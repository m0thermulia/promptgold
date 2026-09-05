"""The three assertions: contains, matches, judge."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from promptspec.models import Model

# Lazily created judge model — see PROMPTSPEC_JUDGE_MODEL below.
_judge_model: Model | None = None

JUDGE_PROMPT = """You are grading an LLM response against a criterion.

Criterion: {criterion}

Response to grade:
\"\"\"
{response}
\"\"\"

Answer in exactly this format:
VERDICT: PASS or FAIL
REASON: one sentence"""


@dataclass
class Verdict:
    """Result of a judge() call."""

    passed: bool
    reason: str

    def __bool__(self) -> bool:
        return self.passed


def contains(response: str, needle: str | re.Pattern[str]) -> bool:
    """True if `needle` (substring or compiled regex) appears in `response`."""
    if isinstance(needle, re.Pattern):
        return bool(needle.search(response))
    return needle in response


def matches(response: str, pattern: str) -> bool:
    """True if `pattern` (regex) matches anywhere in `response`."""
    return bool(re.search(pattern, response))


def resolve_judge_model(model: Model | str | None) -> Model:
    """Pick the judge model.

    Default: whatever PROMPTSPEC_JUDGE_MODEL says, else openai:gpt-4o-mini.
    WARNING: if you judge with the same model under test, the model grades its
    own homework — biased. Set PROMPTSPEC_JUDGE_MODEL to a different model for
    independence.
    """
    global _judge_model
    from promptspec.models import Model

    if isinstance(model, Model):
        return model
    if isinstance(model, str):
        return Model(model)
    if _judge_model is None:
        _judge_model = Model(os.environ.get("PROMPTSPEC_JUDGE_MODEL", "openai:gpt-4o-mini"))
    return _judge_model


def judge(response: str, criterion: str, model: Model | str | None = None) -> Verdict:
    """LLM-as-judge: does `response` satisfy `criterion`? Returns a Verdict.

    Verdict is truthy, so `assert judge(...)` works. Verdict.reason explains why.

    Binary (PASS/FAIL) rather than a 1-5 score: LLM judges on numeric scales are
    bimodal and drift between judge-model versions. Binary verdicts are stable.
    For gradation, run N times and look at the pass rate.
    """
    from promptspec.core import get_active_context

    m = resolve_judge_model(model)
    raw = m.complete(system=JUDGE_PROMPT.format(criterion=criterion, response=response))

    verdict_match = re.search(r"VERDICT:\s*(PASS|FAIL)", raw, re.IGNORECASE)
    if not verdict_match:
        raise ValueError(f"Judge returned no verdict: {raw!r}")
    reason_match = re.search(r"REASON:\s*(.+)", raw)

    v = Verdict(
        passed=verdict_match.group(1).upper() == "PASS",
        reason=reason_match.group(1).strip() if reason_match else "",
    )

    # Record the verdict so the plugin can golden-file it
    ctx = get_active_context()
    if ctx is not None:
        ctx.verdicts.append(
            {"criterion": criterion, "passed": v.passed, "reason": v.reason}
        )

    return v
