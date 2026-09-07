"""Tests for the HTML report renderer."""

from __future__ import annotations

from promptgold.report import render
from promptgold.results import PromptTestResult, RunResults, VerdictResult


def _sample_run() -> RunResults:
    run = RunResults()
    run.tests.append(
        PromptTestResult(
            nodeid="tests/test_a.py::test_passing",
            model="openai:gpt-4o-mini",
            verdicts=[VerdictResult("empathetic?", True, True, "kind")],
            cost_usd=0.0003,
            latency_ms=1200.0,
            cassette="replayed",
        )
    )
    run.tests.append(
        PromptTestResult(
            nodeid="tests/test_b.py::test_regressed",
            model="openai:gpt-4o-mini",
            verdicts=[VerdictResult("refuses <script> jailbreak?", True, False, "broke")],
            cost_usd=0.0011,
            latency_ms=2100.0,
            cassette="recorded",
        )
    )
    return run


def test_is_self_contained_html():
    out = render(_sample_run())
    assert out.startswith("<!DOCTYPE html>")
    assert "<style>" in out
    assert "http://" not in out and "https://" not in out  # no CDN links
    assert "<script src" not in out


def test_contains_stats_and_tests():
    out = render(_sample_run())
    assert "test_passing" in out
    assert "test_regressed" in out
    assert "$0.0014" in out
    assert ">2</div><div class=\"label\">tests" in out or ">2<" in out


def test_regression_arrow_shown():
    out = render(_sample_run())
    assert "PASS → FAIL" in out
    assert "regress" in out


def test_html_escaping():
    out = render(_sample_run())
    # criterion contains <script> — must be escaped, not injected
    assert "<script> jailbreak" not in out
    assert "&lt;script&gt;" in out


def test_branding():
    out = render(_sample_run())
    assert "#d4a017" in out  # gold
    assert "promptgold" in out
    assert "built by hope only" in out
    assert "monospace" in out  # terminal-brutalist world


def test_error_test_rendered():
    run = RunResults()
    run.tests.append(
        PromptTestResult(nodeid="t.py::test_boom", model="m", error="ValueError: boom")
    )
    out = render(run)
    assert "ValueError: boom" in out
    assert 'stamp fail' in out


def test_cassette_stats_shown():
    out = render(_sample_run())
    assert "1 replayed · 1 recorded" in out
