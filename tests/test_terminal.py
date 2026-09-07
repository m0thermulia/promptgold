"""Tests for the terminal renderer — structure, colors, summary math."""

from __future__ import annotations

from promptgold.results import PromptTestResult, RunResults, VerdictResult
from promptgold.terminal import render


def _sample_run() -> RunResults:
    run = RunResults()
    run.tests.append(
        PromptTestResult(
            nodeid="tests/test_a.py::test_passing",
            model="openai:gpt-4o-mini",
            verdicts=[VerdictResult("empathetic?", True, True, "ok")],
            cost_usd=0.0003,
            latency_ms=1200.0,
            cassette="replayed",
        )
    )
    run.tests.append(
        PromptTestResult(
            nodeid="tests/test_b.py::test_regressed",
            model="openai:gpt-4o-mini",
            verdicts=[VerdictResult("refuses jailbreak?", True, False, "broke")],
            cost_usd=0.0011,
            latency_ms=2100.0,
            cassette="recorded",
        )
    )
    return run


def test_plain_render_structure():
    out = render(_sample_run(), use_color=False)
    assert "promptgold" in out
    assert "test_passing" in out
    assert "test_regressed" in out
    assert "2 tests" in out
    assert "1 passed" in out
    assert "1 failed" in out
    assert "$0.0014" in out
    assert "1 replayed, 1 recorded" in out


def test_regression_shown_with_arrow():
    out = render(_sample_run(), use_color=False)
    assert "'refuses jailbreak?': PASS → FAIL" in out


def test_passing_verdicts_not_detailed():
    out = render(_sample_run(), use_color=False)
    assert "'empathetic?'" not in out


def test_color_codes_present_when_enabled():
    out = render(_sample_run(), use_color=True)
    assert "\033[32m" in out  # green
    assert "\033[31m" in out  # red
    assert "\033[33m" in out  # gold
    assert "\033[0m" in out  # reset


def test_no_color_codes_when_disabled():
    out = render(_sample_run(), use_color=False)
    assert "\033[" not in out


def test_icons():
    out = render(_sample_run(), use_color=False)
    assert "✓ test_passing" in out
    assert "✗ test_regressed" in out


def test_error_test_renders():
    run = RunResults()
    run.tests.append(
        PromptTestResult(
            nodeid="t.py::test_boom",
            model="m",
            error="ValueError: judge returned no verdict",
        )
    )
    out = render(run, use_color=False)
    assert "✗ test_boom" in out
    assert "ValueError: judge returned no verdict" in out
    assert "1 failed" in out


def test_no_cost_no_cassette_minimal_summary():
    run = RunResults()
    run.tests.append(PromptTestResult(nodeid="t.py::test_x", model="m"))
    out = render(run, use_color=False)
    assert "1 tests" in out
    assert "$" not in out.split("──")[-1]  # no cost in summary line
