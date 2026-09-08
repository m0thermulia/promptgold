"""E2E: --promptgold-markdown writes a PR-comment-ready summary file."""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).parent.parent


def _run_pytest(cwd: Path, *args: str) -> subprocess.CompletedProcess:
    env = {k: v for k, v in os.environ.items() if not k.startswith("PYTEST_")}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return subprocess.run(
        [sys.executable, "-m", "pytest", *args],
        cwd=cwd, capture_output=True, text=True, env=env,
    )


def test_markdown_summary_written(tmp_path):
    (tmp_path / "test_p.py").write_text(
        "import promptgold.models\n"
        "from promptgold import prompt_test, judge\n"
        "\n"
        "def fake_init(self, spec, **kw):\n"
        "    self.provider, self.name = spec.split(':', 1)\n"
        "    self.spec = spec\n"
        "    self.temperature, self.max_tokens, self.extra = 0.0, 100, kw\n"
        "    self.last_usage = {'input': 10, 'output': 5}\n"
        "\n"
        "def fake_complete(self, system='', user='', **kw):\n"
        "    if 'VERDICT' in system:\n"
        "        return 'VERDICT: PASS\\nREASON: stub'\n"
        "    return 'refund ok'\n"
        "\n"
        "promptgold.models.Model.__init__ = fake_init\n"
        "promptgold.models.Model.complete = fake_complete\n"
        "\n"
        "@prompt_test(model='openai:gpt-4o-mini')\n"
        "def test_demo(llm):\n"
        "    r = llm.complete(user='hi')\n"
        "    judge(r, 'Is it helpful?', model=llm.model)\n"
    )
    md = tmp_path / "comment.md"
    result = _run_pytest(tmp_path, "test_p.py", f"--promptgold-markdown={md}", "-q")
    assert result.returncode == 0, result.stdout + result.stderr
    assert md.exists()
    body = md.read_text()
    assert "🪙 promptgold ✅" in body
    assert "`test_demo`" in body
    assert "built by hope only" in body
