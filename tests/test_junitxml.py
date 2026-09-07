"""CI integration: prompt tests must appear in pytest's built-in JUnit XML.

promptgold doesn't ship its own XML writer — pytest's --junitxml already
captures prompt tests, including GoldenMismatch failures. These tests lock
that contract so a future refactor can't silently break CI reporting.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent

PASS_E2E = '''
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
def test_empathy(llm):
    r = llm.complete(user="hi")
    judge(r, "Is this empathetic?", model=llm.model)
'''


def _run_pytest(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    # Scrub parent-pytest env vars: an inherited PYTEST_CURRENT_TEST leaks into
    # the nested run and can change plugin behavior. PYTHONDONTWRITEBYTECODE
    # avoids stale .pyc reuse when a test rewrites a file with same size/mtime
    # (e.g. swapping "PASS" for "FAIL" between runs).
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    # Remove any cached bytecode from prior runs of this project dir.
    for pycache in cwd.rglob("__pycache__"):
        shutil.rmtree(pycache, ignore_errors=True)
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd,
        capture_output=True,
        text=True,
        env=env,
    )


def _make_project(tmp_path: Path, verdict: str) -> Path:
    (tmp_path / "test_prompts.py").write_text(PASS_E2E.format(verdict=verdict))
    return tmp_path


def test_junitxml_includes_prompt_tests(tmp_path):
    proj = _make_project(tmp_path, "PASS")
    xml = tmp_path / "report.xml"
    result = _run_pytest(proj, "test_prompts.py", f"--junitxml={xml}", "-q")
    assert result.returncode == 0, result.stdout + result.stderr
    content = xml.read_text()
    assert "test_empathy" in content
    assert "<testsuite" in content


def test_junitxml_captures_golden_mismatch(tmp_path):
    """A verdict flip vs the golden file must surface as a <failure> in XML."""
    # 1. Bless with a PASS judge
    proj = _make_project(tmp_path, "PASS")
    bless = _run_pytest(proj, "test_prompts.py", "--bless", "-q")
    assert bless.returncode == 0, bless.stdout + bless.stderr

    # 2. Re-run with a FAIL judge (bypassing cassettes — they replay the
    # blessed PASS by design) — golden gate should fail the build
    _make_project(tmp_path, "FAIL")
    xml = tmp_path / "fail.xml"
    result = _run_pytest(
        proj, "test_prompts.py", f"--junitxml={xml}", "--no-cassette", "-q"
    )

    assert result.returncode != 0, (
        f"STDOUT:\n{result.stdout}\nSTDERR:\n{result.stderr}"
    )
    content = xml.read_text()
    assert "GoldenMismatch" in content
    assert "<failure" in content