"""Tests for the markdown (PR comment) renderer."""

from __future__ import annotations

from promptgold.markdown import render
from promptgold.results import PromptTestResult, RunResults, VerdictResult


def _run_passing() -> RunResults:
    run = RunResults()
    run.tests.append(
        PromptTestResult(
            nodeid="tests/test_a.py::test_empathy",
            model="openai:gpt-4o-mini",
            verdicts=[VerdictResult("empathetic?", True, True, "kind")],
            cost_usd=0.0003,
            latency_ms=1200.0,
            cassette="replayed",
        )
    )
    return run


def _run_regressed() -> RunResults:
    run = _run_passing()
    run.tests.append(
        PromptTestResult(
            nodeid="tests/test_a.py::test_jailbreak",
            model="openai:gpt-4o-mini",
            verdicts=[VerdictResult("refuses <b>attack</b>?", True, False, "broke character")],
            cost_usd=0.0011,
            cassette="recorded",
        )
    )
    return run


def test_passing_comment_header():
    out = render(_run_passing())
    assert "🪙 promptgold ✅" in out
    assert "**1** tests" in out
    assert "1 failed" not in out


def test_failing_comment_header():
    out = render(_run_regressed())
    assert "❌" in out
    assert "**1** failed" in out


def test_table_shape():
    out = render(_run_regressed())
    assert "| test | verdict | cost | source |" in out
    assert "`test_empathy`" in out
    assert "`test_jailbreak`" in out
    assert "replayed" in out and "recorded" in out


def test_regression_shown_in_what_broke():
    out = render(_run_regressed())
    assert "What broke" in out
    assert "→ **FAIL**" in out
    assert "broke character" in out


def test_html_escaped_in_table():
    """A criterion with HTML must be neutralized — wrapped in a code span,
    which GitHub renders literally instead of executing as HTML."""
    out = render(_run_regressed())
    assert "`refuses <b>attack</b>?`" in out


def test_error_test_listed():
    run = RunResults()
    run.tests.append(
        PromptTestResult(nodeid="t.py::test_boom", model="m", error="ValueError: boom")
    )
    out = render(run)
    assert "ValueError: boom" in out
    assert "❌" in out


def test_cost_summary():
    out = render(_run_regressed())
    assert "$0.0014" in out


def test_motto_footer():
    assert "built by hope only" in render(_run_passing())


def test_repeated_verdicts_compact():
    """Adversarial tests produce many identical verdicts — show '5× PASS', not a wall."""
    run = RunResults()
    run.tests.append(
        PromptTestResult(
            nodeid="t.py::test_resists",
            model="m",
            verdicts=[VerdictResult(f"c{i}", True, True, "") for i in range(5)],
        )
    )
    out = render(run)
    assert "5× PASS" in out
    assert out.count("PASS") == 1  # compacted, not repeated


def test_truncates_huge_runs():
    run = RunResults()
    for i in range(200):
        run.tests.append(
            PromptTestResult(
                nodeid=f"tests/t{i}.py::test_case_{i}", model="m", cassette="replayed"
            )
        )
    out = render(run)
    assert "150 more" in out  # 200 - MAX_TESTS(50)
    assert out.count("| ✅ `test_case_") == 50
