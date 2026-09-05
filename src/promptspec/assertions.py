"""The three assertions: contains, matches, judge."""

from __future__ import annotations

import re
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from promptspec.models import Model

# Lazily created judge model — uses the cheapest sensible default.
_judge_model: Model | None = None

JUDGE_PROMPT = """You are grading an LLM response on a scale of 1 to 5.

Criterion: {criterion}

Response to grade:
\"\"\"
{response}
\"\"\"

Reply with ONLY a single integer from 1 (completely fails) to 5 (fully satisfies)."""


def contains(response: str, needle: str | re.Pattern[str]) -> bool:
    """True if `needle` (substring or compiled regex) appears in `response`."""
    if isinstance(needle, re.Pattern):
        return bool(needle.search(response))
    return needle in response


def matches(response: str, pattern: str) -> bool:
    """True if `pattern` (regex) matches anywhere in `response`."""
    return bool(re.search(pattern, response))


def judge(response: str, criterion: str, model: Model | str | None = None) -> int:
    """LLM-as-judge: grade `response` against `criterion`, return 1-5.

    Uses a judge model (defaults to openai:gpt-4o-mini, overridable via
    PROMPTSPEC_JUDGE_MODEL env var or the `model` argument).
    """
    global _judge_model
    from promptspec.models import Model

    if isinstance(model, Model):
        m = model
    elif isinstance(model, str):
        m = Model(model)
    else:
        import os

        if _judge_model is None:
            _judge_model = Model(os.environ.get("PROMPTSPEC_JUDGE_MODEL", "openai:gpt-4o-mini"))
        m = _judge_model

    raw = m.complete(system=JUDGE_PROMPT.format(criterion=criterion, response=response))
    digits = re.search(r"[1-5]", raw)
    if not digits:
        raise ValueError(f"Judge returned non-score: {raw!r}")
    return int(digits.group())
