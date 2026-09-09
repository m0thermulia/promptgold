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


def test_cassette_path_includes_model_spec(tmp_path, monkeypatch):
    """Two models in one test must not clobber each other's cassette file.

    Regression: the bot model and an independent judge model both wrote to
    _slug(nodeid), so the judge's save() overwrote every bot response — the
    cassette ended up containing only verdicts and the test could never
    replay offline again.
    """
    from promptgold.cassettes import CassetteModel, _slug

    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)

    class Fake:
        def __init__(self, spec):
            self.spec = spec
            self.last_usage = None

        def complete(self, system="", user="", **kw):
            return f"reply from {self.spec}"

    bot = CassetteModel(Fake("openai:bot-model"), "tests/t.py::test_x")
    judge = CassetteModel(Fake("openai:judge-model"), "tests/t.py::test_x")

    assert bot.path != judge.path, "both models wrote to the same file"
    assert _slug("tests/t.py::test_x", "openai:bot-model").endswith("__openai_bot-model.json")
    assert _slug("tests/t.py::test_x") == "tests_t.py_test_x.json"  # back-compat


def test_two_models_each_keep_their_own_responses(tmp_path, monkeypatch):
    from promptgold.cassettes import CassetteModel

    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)

    class Fake:
        def __init__(self, spec):
            self.spec = spec
            self.last_usage = None

        def complete(self, system="", user="", **kw):
            return f"reply from {self.spec}"

    nodeid = "tests/t.py::test_two_models"
    bot = CassetteModel(Fake("openai:bot"), nodeid)
    jud = CassetteModel(Fake("openai:judge"), nodeid)

    bot.complete(user="hello")
    jud.complete(system="VERDICT please", user="")
    bot.save()
    jud.save()

    # Re-load from disk: both files exist with their own content intact.
    bot2 = CassetteModel(Fake("openai:bot"), nodeid)
    jud2 = CassetteModel(Fake("openai:judge"), nodeid)
    assert bot2.complete(user="hello") == "reply from openai:bot"
    assert bot2.replayed == 1
    assert jud2.complete(system="VERDICT please", user="") == "reply from openai:judge"
    assert jud2.replayed == 1

def test_legacy_cassette_filename_still_replays(tmp_path, monkeypatch):
    """Cassettes committed before the model-spec filename must still replay.

    If the lookup only knew the new name, every pre-existing committed
    cassette would silently miss and fall through to the live API — the
    exact silent-spend bug class this project refuses to ship.
    """
    from promptgold.cassettes import CassetteModel, _key, _slug

    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)

    class Fake:
        def __init__(self):
            self.spec = "openai:gpt-4o-mini"
            self.last_usage = None
            self.calls = 0

        def complete(self, system="", user="", **kw):
            self.calls += 1
            return "live reply"

    nodeid = "tests/t.py::test_legacy"
    # Write a cassette under the OLD filename (no model spec).
    legacy = tmp_path / _slug(nodeid)
    legacy.write_text(
        json.dumps(
            {
                "model": "openai:gpt-4o-mini",
                "responses": {_key("openai:gpt-4o-mini", "", "hi"): "recorded reply"},
            }
        )
    )

    fake = Fake()
    cm = CassetteModel(fake, nodeid)
    assert cm.complete(user="hi") == "recorded reply"
    assert fake.calls == 0, "legacy cassette missed and hit the live API"


def test_judge_model_is_wrapped_into_the_active_cassette(tmp_path, monkeypatch):
    """An independent judge (PROMPTGOLD_JUDGE_MODEL) must replay offline too.

    Regression: judge() built a fresh raw Model for the env-configured judge,
    so every judge call re-charged the API on every run and failed outright
    with no network — even though the bot's calls replayed fine from
    cassettes. The recommended secure config (separate judge) was the one
    that broke the offline promise.
    """
    import promptgold.models
    from promptgold import cassettes
    from promptgold.assertions import judge
    from promptgold.core import LLMContext, set_active_context

    monkeypatch.setattr(cassettes, "CASSETTE_DIR", tmp_path)
    monkeypatch.setenv("PROMPTGOLD_JUDGE_MODEL", "openai:judge-model")

    calls = {"n": 0}

    class FakeModel:
        def __init__(self, spec, **kw):
            self.spec = spec
            self.last_usage = None

        def complete(self, system="", user="", **kw):
            calls["n"] += 1
            return "VERDICT: PASS\nREASON: looks good"

    # resolve_judge_model builds Model(...) internally; swap the class so no
    # network or credentials are involved.
    monkeypatch.setattr(promptgold.models, "Model", FakeModel)

    class Bot(FakeModel):
        spec = "openai:bot"

    nodeid = "tests/t.py::test_judge_cassette"
    bot = cassettes.get_or_create(Bot("openai:bot"), nodeid)
    ctx = LLMContext(model=bot, nodeid=nodeid)

    # Run 1: judge hits the live model once, records into the cassette.
    set_active_context(ctx)
    try:
        v = judge("some reply", "Is it polite?")
    finally:
        set_active_context(None)
    assert v.passed is True
    assert calls["n"] == 1
    cassettes.save_all(nodeid)
    cassettes.clear(nodeid)

    # Run 2: fresh registry — the judge model must NOT be called again.
    calls["n"] = 0
    bot2 = cassettes.get_or_create(Bot("openai:bot"), nodeid)
    ctx2 = LLMContext(model=bot2, nodeid=nodeid)
    set_active_context(ctx2)
    try:
        v2 = judge("some reply", "Is it polite?")
    finally:
        set_active_context(None)
    assert v2.passed is True
    assert calls["n"] == 0, "judge charged the API again instead of replaying"


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
    cassette = tmp_path / ".promptgold/cassettes/t_prompts_test.py_test_something__stub_model.json"
    # First run: records cassette (golden check warns, still passes).
    assert run_pytest() == 0
    assert cassette.exists()

    # Second run: replay serves the recorded response, no live call needed.
    assert run_pytest() == 0
    data = json.loads(cassette.read_text())
    assert "happy" in next(iter(data["responses"].values()))
