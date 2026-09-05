"""pytest plugin: discovers @prompt_test functions, handles golden files."""

from __future__ import annotations

import inspect
from typing import Any

import pytest

from promptspec import golden
from promptspec.core import LLMContext, set_active_context
from promptspec.models import Model


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("promptspec")
    group.addoption(
        "--bless",
        action="store_true",
        default=False,
        help="Record current judge verdicts as the golden files (commit them).",
    )
    group.addoption(
        "--no-golden-check",
        action="store_true",
        default=False,
        help="Run prompt tests without comparing against golden files.",
    )


class GoldenMismatch(AssertionError):
    pass


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    """Run a prompt test, then bless or check judge verdicts.

    What gates the build: judge verdicts (PASS/FAIL) from the golden files.
    What doesn't: the raw response text. Text changes constantly with LLMs;
    whether the response satisfies the criterion is the signal a human can
    act on. Raw text is still recorded in the golden file for diffing.
    """
    fn = getattr(item, "obj", None)
    if fn is None or not getattr(fn, "_is_promptspec_test", False):
        return

    model_spec = fn._promptspec_model
    model = model_spec if isinstance(model_spec, Model) else Model(model_spec)
    ctx = LLMContext(model=model)

    original = fn.__wrapped__
    sig = inspect.signature(original)
    kwargs = {}
    for name in sig.parameters:
        if name == "llm":
            kwargs[name] = ctx
        elif name in item.funcargs:
            kwargs[name] = item.funcargs[name]
        else:
            raise TypeError(
                f"promptspec test {item.nodeid}: parameter {name!r} is neither "
                "'llm' nor an available fixture"
            )

    set_active_context(ctx)
    try:
        original(**kwargs)
    finally:
        set_active_context(None)

    payload: dict[str, Any] = {
        "model": model.spec,
        "verdicts": ctx.verdicts,
        "responses": [c["response"] for c in ctx.calls],
    }

    if item.config.getoption("--bless"):
        path = golden.save(item.nodeid, payload)
        print(f"\npromptspec: blessed {path}")
        return

    if item.config.getoption("--no-golden-check"):
        return

    expected = golden.load(item.nodeid)
    if expected is None:
        # No golden file yet: pass, but tell the user how to create one.
        print(
            f"\npromptspec: no golden file for {item.nodeid}. "
            "Run `pytest --bless` and commit the result."
        )
        return

    mismatches = _diff_verdicts(expected["verdicts"], payload["verdicts"])
    if mismatches:
        raise GoldenMismatch(
            "Judge verdicts regressed vs golden file:\n" + "\n".join(mismatches)
        )


def _diff_verdicts(expected: list[dict], current: list[dict]) -> list[str]:
    lines = []
    for i, (e, c) in enumerate(zip(expected, current, strict=False)):
        if e["passed"] != c["passed"]:
            lines.append(
                f"  verdict {i} ({e['criterion']!r}): "
                f"{'PASS' if e['passed'] else 'FAIL'} -> "
                f"{'PASS' if c['passed'] else 'FAIL'}"
            )
            if c.get("reason"):
                lines.append(f"    reason now: {c['reason']}")
    if len(expected) != len(current):
        lines.append(f"  verdict count changed: {len(expected)} -> {len(current)}")
    return lines


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "promptspec: mark a test as a prompt regression test"
    )
