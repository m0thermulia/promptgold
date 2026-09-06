"""Offline tests for VCR-style response cassettes."""

from __future__ import annotations

import json

import promptgold.cassettes as cassettes


class FakeModel:
    spec = "fake:model"

    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    def complete(self, system="", user="", **kw):
        self.calls.append((system, user))
        if not self.responses:
            raise AssertionError("real API was called but cassette should have hit")
        return self.responses.pop(0)


def test_first_run_records(tmp_path, monkeypatch):
    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    inner = FakeModel(["hello"])
    m = cassettes.CassetteModel(inner, "t.py::test_a")

    assert m.complete(system="s", user="u") == "hello"
    assert m.recorded == 1 and m.replayed == 0
    path = m.save()
    assert path is not None and path.exists()

    data = json.loads(path.read_text())
    assert data["model"] == "fake:model"
    assert len(data["responses"]) == 1


def test_second_run_replays_without_api(tmp_path, monkeypatch):
    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    inner = FakeModel(["hello"])
    m = cassettes.CassetteModel(inner, "t.py::test_a")
    m.complete(system="s", user="u")
    m.save()

    # Second instance: empty responses, so any real API call would raise.
    m2 = cassettes.CassetteModel(FakeModel([]), "t.py::test_a")
    assert m2.complete(system="s", user="u") == "hello"
    assert m2.replayed == 1 and m2.recorded == 0
    assert m2.save() is None  # nothing new recorded, nothing written


def test_different_prompts_are_separate_entries(tmp_path, monkeypatch):
    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    inner = FakeModel(["a", "b"])
    m = cassettes.CassetteModel(inner, "t.py::test_a")
    assert m.complete(user="one") == "a"
    assert m.complete(user="two") == "b"
    m.save()
    assert len(json.loads(m.path.read_text())["responses"]) == 2


def test_different_tests_get_different_cassettes(tmp_path, monkeypatch):
    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    a = cassettes.CassetteModel(FakeModel([]), "t.py::test_a")
    b = cassettes.CassetteModel(FakeModel([]), "t.py::test_b")
    assert a.path != b.path


def test_plugin_wraps_model(stub_model, tmp_path, monkeypatch):
    """End-to-end through the pytest plugin: first run records, second replays."""
    monkeypatch.chdir(tmp_path)

    def run_pytest(*args):
        import pytest

        return pytest.main([*args])

    (tmp_path / "t_prompts_test.py").write_text(
        "from promptgold import prompt_test, contains\n"
        "@prompt_test(model='stub:model')\n"
        "def test_something(llm):\n"
        "    r = llm.complete(user='hi')\n"
        "    assert contains(r, 'happy')\n"
    )
    cassette = tmp_path / ".promptgold/cassettes/t_prompts_test.py_test_something.json"
    # First run: records cassette (golden check warns, still passes).
    assert run_pytest() == 0
    assert cassette.exists()

    # Second run: replay serves the recorded response, no live call needed.
    assert run_pytest() == 0
    data = json.loads(cassette.read_text())
    assert "happy" in next(iter(data["responses"].values()))
