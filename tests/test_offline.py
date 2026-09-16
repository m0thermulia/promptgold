"""Replay-only mode must fail closed, including independent judge calls."""

from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from promptgold.assertions import JUDGE_PROMPT
from promptgold.cassettes import _key, _slug


@pytest.fixture
def project(tmp_path):
    # Guard the provider boundary even in nested pytest runs. A marker makes
    # accidental calls observable independently of the child's exit status.
    (tmp_path / "conftest.py").write_text(
        "from pathlib import Path\n"
        "import pytest\n"
        "from promptgold.models import Model\n"
        "\n"
        "@pytest.fixture(autouse=True)\n"
        "def forbid_model_calls(monkeypatch):\n"
        "    def forbidden(self, **kwargs):\n"
        "        Path('model-called').write_text(self.spec)\n"
        "        raise AssertionError('underlying model called')\n"
        "    monkeypatch.setattr(Model, 'complete', forbidden)\n"
    )
    (tmp_path / "test_prompt.py").write_text(
        "from promptgold import prompt_test\n"
        "@prompt_test(model='openai:bot')\n"
        "def test_prompt(llm):\n"
        "    assert llm.complete(user='hello') == 'recorded reply'\n"
    )
    return tmp_path


def run_pytest(project, *args, extra_env=None):
    env = {
        k: v for k, v in os.environ.items()
        if not k.startswith(("PYTEST_", "PROMPTGOLD_", "OPENAI_", "ANTHROPIC_", "OLLAMA_"))
    }
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, "-m", "pytest", "-q", *args],
        cwd=project, capture_output=True, text=True, env=env, timeout=30,
    )


def seed_cassette(project, spec="openai:bot", *, system="", user="hello",
                  response="recorded reply", legacy=False):
    path = project / ".promptgold/cassettes" / _slug(
        "test_prompt.py::test_prompt", "" if legacy else spec
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({
        "model": spec, "responses": {_key(spec, system, user): response},
    }))
    return path


def test_offline_missing_cassette_never_calls_model(project):
    result = run_pytest(project, "--offline")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "OfflineCassetteMiss" in output
    assert "openai:bot" in output
    assert "test_prompt.py::test_prompt" in output
    assert "--offline" in output
    assert not (project / "model-called").exists()
    assert not (project / ".promptgold").exists()


def test_offline_rejects_no_cassette_before_collection(project):
    # A configuration error must stop even collection-time user code.
    (project / "test_prompt.py").write_text("raise AssertionError('test was collected')\n")
    result = run_pytest(project, "--offline", "--no-cassette")
    output = result.stdout + result.stderr
    assert result.returncode == 4, output
    assert "--offline cannot be combined with --no-cassette" in output
    assert "test was collected" not in output
    assert not (project / "model-called").exists()


@pytest.mark.parametrize("recorded", [False, True], ids=["miss", "hit"])
@pytest.mark.parametrize("selection", ["env", "string", "model", "wrapped", "cached"])
def test_offline_judge_never_calls_model(project, selection, recorded):
    seed_cassette(project)
    judge_args = {
        "env": "",
        "string": ", model='openai:judge'",
        "model": ", model=Model('openai:judge')",
        "wrapped": ", model=CassetteModel(Model('openai:judge'), 'other-test')",
        "cached": ", model=get_or_create(Model('openai:judge'), llm.nodeid)",
    }
    (project / "test_prompt.py").write_text(
        "from promptgold import Model, prompt_test, judge\n"
        "from promptgold.cassettes import CassetteModel, get_or_create\n"
        "@prompt_test(model='openai:bot')\n"
        "def test_prompt(llm):\n"
        "    r = llm.complete(user='hello')\n"
        f"    assert judge(r, 'Is it helpful?'{judge_args[selection]})\n"
    )
    if recorded:
        seed_cassette(
            project, "openai:judge", user="",
            system=JUDGE_PROMPT.format(criterion="Is it helpful?", response="recorded reply"),
            response="VERDICT: PASS\nREASON: recorded independent judge",
        )
    env = {"PROMPTGOLD_JUDGE_MODEL": "openai:judge"} if selection == "env" else {}
    before = {p: p.read_bytes() for p in (project / ".promptgold").rglob("*") if p.is_file()}
    result = run_pytest(project, "--offline", extra_env=env)
    output = result.stdout + result.stderr
    if recorded:
        assert result.returncode == 0, output
        assert "1 passed" in output
    else:
        assert result.returncode == 1, output
        assert "OfflineCassetteMiss" in output, output
        assert "openai:judge" in output
    assert not (project / "model-called").exists()
    after = {p: p.read_bytes() for p in (project / ".promptgold").rglob("*") if p.is_file()}
    assert after == before


def test_cached_wrapper_cannot_bypass_offline(tmp_path, monkeypatch):
    from promptgold import cassettes

    class ForbiddenModel:
        spec = "openai:judge"
        calls = 0

        def complete(self, **kwargs):
            self.calls += 1
            raise AssertionError("underlying model called")

    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    inner = ForbiddenModel()
    nodeid = "test_cached.py::test_prompt"
    try:
        cached = cassettes.get_or_create(inner, nodeid)
        offline = cassettes.get_or_create(inner, nodeid, offline=True)
        assert offline is cached
        with pytest.raises(cassettes.OfflineCassetteMiss):
            offline.complete(user="not recorded")
        # A later caller using the default must not weaken the policy.
        default = cassettes.get_or_create(inner, nodeid)
        with pytest.raises(cassettes.OfflineCassetteMiss):
            default.complete(user="not recorded either")
        assert inner.calls == 0
        assert offline.recorded == offline.replayed == 0
        assert offline.save() is None
    finally:
        cassettes.clear(nodeid)


@pytest.mark.parametrize("legacy", [False, True], ids=["current", "legacy"])
def test_offline_replays_without_writing(project, legacy):
    path = seed_cassette(project, legacy=legacy)
    before = path.read_bytes()
    result = run_pytest(project, "--offline")
    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 passed" in result.stdout
    assert not (project / "model-called").exists()
    assert path.read_bytes() == before
    assert list((project / ".promptgold").rglob("*.json")) == [path]


def test_offline_missing_entry_never_records(project):
    path = seed_cassette(project, user="old prompt")
    before = path.read_bytes()
    result = run_pytest(project, "--offline")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "OfflineCassetteMiss" in output
    assert not (project / "model-called").exists()
    assert path.read_bytes() == before


def test_offline_corrupt_cassette_never_calls_model(project):
    path = seed_cassette(project)
    path.write_text("not valid json")
    result = run_pytest(project, "--offline")
    output = result.stdout + result.stderr
    assert result.returncode == 1, output
    assert "JSONDecodeError" in output
    assert not (project / "model-called").exists()
    assert path.read_text() == "not valid json"
