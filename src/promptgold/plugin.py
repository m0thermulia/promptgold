"""pytest plugin: discovers @prompt_test functions, handles golden files."""

from __future__ import annotations

import inspect
from pathlib import Path
from typing import Any

import pytest

from promptgold import cassettes, golden, terminal
from promptgold.core import LLMContext, set_active_context
from promptgold.models import Model
from promptgold.results import PromptTestResult, RunResults, VerdictResult


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("promptgold")
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
    group.addoption(
        "--no-cassette",
        action="store_true",
        default=False,
        help="Always call the live API instead of replaying response cassettes.",
    )
    group.addoption(
        "--promptgold-report",
        metavar="PATH",
        default=None,
        help="Write a self-contained HTML report to PATH after the run.",
    )
    group.addoption(
        "--promptgold-markdown",
        metavar="PATH",
        default=None,
        help="Write a GitHub-flavored markdown summary to PATH (for PR comments).",
    )


class GoldenMismatch(AssertionError):
    pass


# Collected results for the terminal summary (and future HTML report).
_run = RunResults()


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    """Run promptgold tests via our runner; let everything else through.

    This hookimpl is NOT a wrapper: for promptgold tests we run the function
    ourselves and then mark the item so pytest's default runtest_call skips
    re-executing the body (which would double API spend and double verdicts).
    """
    fn = getattr(item, "obj", None)
    if fn is None or not getattr(fn, "_is_promptgold_test", False):
        return
    _run_prompt_test(item, fn)
    # Prevent pytest's default runtest_call from running the body a second
    # time: point item.obj at a no-op with an empty signature.
    item.obj = _already_ran


def _already_ran(**kwargs: Any) -> None:
    """Placeholder swapped in after a promptgold test has been executed.

    Accepts and ignores the fixture kwargs pytest's default runtest_call
    passes to item.obj()."""


def _run_prompt_test(item: pytest.Item, fn: Any) -> None:
    """Execute one @prompt_test function: cassettes, verdicts, golden gate."""
    model_spec = fn._promptgold_model
    model = model_spec if isinstance(model_spec, Model) else Model(model_spec)
    if not item.config.getoption("--no-cassette"):
        model = cassettes.get_or_create(model, item.nodeid)
    ctx = LLMContext(model=model, nodeid=item.nodeid)

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
                f"promptgold test {item.nodeid}: parameter {name!r} is neither "
                "'llm' nor an available fixture"
            )

    test_error: str | None = None
    set_active_context(ctx)
    try:
        original(**kwargs)
    except Exception as e:
        # First line only: pytest's assertion repr is multi-line and would
        # wreck table cells and PR comments.
        msg = str(e).splitlines()[0] if str(e) else type(e).__name__
        test_error = f"{type(e).__name__}: {msg}"
        raise
    finally:
        set_active_context(None)
        if not item.config.getoption("--no-cassette"):
            # Flush every cassette for this test — the model under test AND
            # any judge model that recorded into it.
            for path in cassettes.save_all(item.nodeid):
                print(f"\npromptgold: recorded -> {path}")
            cassettes.clear(item.nodeid)
        # ALWAYS record the result — including failures — or broken tests
        # silently vanish from the terminal summary, HTML report, and PR
        # comment (the one place the failure matters most).
        result = PromptTestResult(
            nodeid=item.nodeid,
            model=model.spec,
            cost_usd=ctx.total_cost,
            latency_ms=sum(c["latency_ms"] for c in ctx.calls),
            cassette=(
                "recorded"
                if isinstance(model, cassettes.CassetteModel) and model.recorded
                else "replayed"
                if isinstance(model, cassettes.CassetteModel)
                else "live"
            ),
            error=test_error,
        )
        # Even on failure, surface whatever verdicts were recorded so the
        # report shows WHICH criterion flipped. On success the golden-check
        # paths below extend verdicts (with expected values) instead.
        if test_error is not None:
            result.verdicts.extend(_verdict_results(ctx, None))
        _run.tests.append(result)

    payload: dict[str, Any] = {
        "model": model.spec,
        "verdicts": ctx.verdicts,
        "responses": [c["response"] for c in ctx.calls],
        "cost_usd": ctx.total_cost,
    }

    if item.config.getoption("--bless"):
        path = golden.save(item.nodeid, payload)
        print(f"\npromptgold: blessed {path}")
        return

    if item.config.getoption("--no-golden-check"):
        result.verdicts.extend(_verdict_results(ctx, None))
        return

    expected = golden.load(item.nodeid)
    if expected is None:
        # No golden file yet: pass, but tell the user how to create one.
        print(
            f"\npromptgold: no golden file for {item.nodeid}. "
            "Run `pytest --bless` and commit the result."
        )
        result.verdicts.extend(_verdict_results(ctx, None))
        return

    result.verdicts.extend(_verdict_results(ctx, expected["verdicts"]))

    mismatches = _diff_verdicts(expected["verdicts"], payload["verdicts"])
    if mismatches:
        raise GoldenMismatch(
            "Judge verdicts regressed vs golden file:\n" + "\n".join(mismatches)
        )


def _verdict_results(ctx: LLMContext, expected: list[dict] | None) -> list[VerdictResult]:
    out = []
    if expected is None:
        for v in ctx.verdicts:
            out.append(
                VerdictResult(
                    criterion=v["criterion"],
                    expected=None,
                    actual=v["passed"],
                    reason=v.get("reason", ""),
                )
            )
    else:
        for e, c in zip(expected, ctx.verdicts, strict=False):
            out.append(
                VerdictResult(
                    criterion=c["criterion"],
                    expected=e["passed"],
                    actual=c["passed"],
                    reason=c.get("reason", ""),
                )
            )
    return out


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


def pytest_terminal_summary(terminalreporter: Any, config: pytest.Config) -> None:
    if _run.tests:
        terminalreporter.write_line("")
        for line in terminal.render(_run).splitlines():
            terminalreporter.write_line(line)

    report_path = config.getoption("--promptgold-report")
    if report_path and _run.tests:
        from promptgold import report

        out = Path(report_path)
        out.write_text(report.render(_run))
        terminalreporter.write_line(f"promptgold: HTML report -> {out}")

    md_path = config.getoption("--promptgold-markdown")
    if md_path and _run.tests:
        from promptgold import markdown

        out = Path(md_path)
        out.write_text(markdown.render(_run))
        terminalreporter.write_line(f"promptgold: markdown summary -> {out}")


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "promptgold: mark a test as a prompt regression test"
    )
