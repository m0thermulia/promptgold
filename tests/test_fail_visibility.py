"""Regression: failing prompt tests must still appear in reports/summaries.

Bug found during the PR-comment demo: a test that raised (assert judge(...)
failed) never got appended to RunResults, so the PR comment showed "5 tests
passed" for a 6-test suite with one failure — the failure vanished from the
one place it mattered most.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

FAILING_PROJECT = '''
import promptgold.models
from promptgold import prompt_test, judge

def fake_init(self, spec, **kw):
    self.provider, self.name = spec.split(":", 1)
    self.spec = spec
    self.temperature, self.max_tokens, self.extra = 0.0, 100, kw
    self.last_usage = {{"input": 10, "output": 5}}

def fake_complete(self, system="", user="", **kw):
    if "VERDICT" in system:
        return "VERDICT: {verdict}\\nREASON: stub"
    return "refund ok"

promptgold.models.Model.__init__ = fake_init
promptgold.models.Model.complete = fake_complete

@prompt_test(model="openai:gpt-4o-mini")
def test_will_fail(llm):
    r = llm.complete(user="hi")
    assert judge(r, "Is it empathetic?", model=llm.model)
'''


def _run_pytest(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def test_failing_test_appears_in_reports(tmp_path):
    (tmp_path / "test_f.py").write_text(FAILING_PROJECT.format(verdict="FAIL"))
    md = tmp_path / "comment.md"
    html = tmp_path / "report.html"

    result = _run_pytest(
        tmp_path, "test_f.py",
        f"--promptgold-markdown={md}",
        f"--promptgold-report={html}",
        "-q",
    )
    assert result.returncode != 0  # the test genuinely failed

    # The failure must be VISIBLE in both renderers, not silently dropped.
    body = md.read_text()
    assert "test_will_fail" in body
    assert "❌" in body
    assert "What broke" in body
    assert "AssertionError" in body  # the failed assert is reported as an error

    page = html.read_text()
    assert "test_will_fail" in page
    assert "stamp fail" in page
