"""The three assertions: contains, matches, judge."""

from __future__ import annotations

import os
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from promptgold.models import Model

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

    Default: whatever PROMPTGOLD_JUDGE_MODEL says, else openai:gpt-4o-mini.
    Read fresh on every call — caching it in a module global meant the env var
    was honored only for the first judge() in a process and silently ignored
    afterwards, so a test run could grade with the wrong model.
    WARNING: if you judge with the same model under test, the model grades its
    own homework — biased. Set PROMPTGOLD_JUDGE_MODEL to a different model for
    independence.
    """
    from promptgold.models import Model

    if isinstance(model, str):
        return Model(model)
    if model is not None:
        # Any model-like object with .complete (Model, CassetteModel, stubs)
        return model
    return Model(os.environ.get("PROMPTGOLD_JUDGE_MODEL", "openai:gpt-4o-mini"))


def judge(response: str, criterion: str, model: Model | str | None = None) -> Verdict:
    """LLM-as-judge: does `response` satisfy `criterion`? Returns a Verdict.

    Verdict is truthy, so `assert judge(...)` works. Verdict.reason explains why.

    Binary (PASS/FAIL) rather than a 1-5 score: LLM judges on numeric scales are
    bimodal and drift between judge-model versions. Binary verdicts are stable.
    For gradation, run N times and look at the pass rate.

    Model resolution order: explicit `model=` arg > PROMPTGOLD_JUDGE_MODEL env >
    the active prompt test's model (so cassette replay covers judge calls too).
    Set PROMPTGOLD_JUDGE_MODEL to a different provider for judge independence.

    Whichever model wins, if a cassette is active for this test the judge is
    wrapped into it too — otherwise an independent judge model would re-charge
    on every run and break offline replay (and CI), defeating the point.
    """
    from promptgold import cassettes
    from promptgold.core import get_active_context

    ctx = get_active_context()
    if model is None and "PROMPTGOLD_JUDGE_MODEL" not in os.environ and ctx is not None:
        m = ctx.model
    else:
        m = resolve_judge_model(model)
        # Route an independent judge model through the active cassette.
        if ctx is not None and ctx.nodeid is not None and m is not ctx.model:
            m = cassettes.get_or_create(m, ctx.nodeid)
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
