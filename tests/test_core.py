"""Unit tests for promptgold core — run offline with a stub provider."""

from __future__ import annotations

import re

import pytest

from promptgold import Model, contains, matches, prompt_test
from promptgold.models import Model as ModelClass


class StubModel(ModelClass):
    """A model that returns canned responses — no API keys needed."""

    def __init__(self, response: str = "hello world"):
        self.provider = "stub"
        self.name = "stub"
        self.spec = "stub:stub"
        self.temperature = 0.0
        self.max_tokens = 100
        self.extra = {}
        self._response = response

    def complete(self, system: str = "", user: str = "", **kwargs) -> str:
        return self._response


def test_model_spec_parsing():
    m = Model("openai:gpt-4o-mini")
    assert m.provider == "openai"
    assert m.name == "gpt-4o-mini"


def test_model_spec_requires_colon():
    with pytest.raises(ValueError, match="provider:name"):
        Model("gpt-4o-mini")


def test_unknown_provider_rejected():
    m = Model.__new__(Model)
    m.provider, m.name, m.spec = "bogus", "x", "bogus:x"
    m.temperature, m.max_tokens, m.extra = 0.0, 100, {}
    with pytest.raises(ValueError, match="Unknown provider"):
        m.complete(user="hi")


def test_contains_substring():
    assert contains("hello world", "world")
    assert not contains("hello world", "mars")


def test_contains_regex():
    assert contains("order #1234", re.compile(r"#\d+"))


def test_matches():
    assert matches("refund issued: $50", r"\$\d+")
    assert not matches("no refund", r"\$\d+")


def test_prompt_test_decorator_marks_function():
    @prompt_test(model="stub:stub")
    def my_test(llm):
        pass

    assert getattr(my_test, "_is_promptgold_test", False)
    assert my_test._promptgold_model == "stub:stub"


def test_llm_context_records_calls():
    from promptgold.core import LLMContext

    ctx = LLMContext(model=StubModel("canned"))
    out = ctx.complete(system="s", user="u")
    assert out == "canned"
    assert len(ctx.calls) == 1
    assert ctx.calls[0]["response"] == "canned"
    assert ctx.last_response == "canned"


def test_judge_pass_verdict():
    from promptgold.assertions import judge

    v = judge("anything", "Is it good?", model=StubModel("VERDICT: PASS\nREASON: it's great"))
    assert v.passed is True
    assert bool(v) is True
    assert v.reason == "it's great"


def test_judge_fail_verdict():
    from promptgold.assertions import judge

    v = judge("anything", "Is it good?", model=StubModel("VERDICT: FAIL\nREASON: it's bad"))
    assert v.passed is False
    assert bool(v) is False


def test_judge_rejects_bad_output():
    from promptgold.assertions import judge

    with pytest.raises(ValueError, match="no verdict"):
        judge("anything", "Is it good?", model=StubModel("i dunno"))


def test_judge_records_verdict_in_active_context():
    from promptgold.assertions import judge
    from promptgold.core import LLMContext, set_active_context

    ctx = LLMContext(model=StubModel("x"))
    set_active_context(ctx)
    try:
        judge("resp", "Is it polite?", model=StubModel("VERDICT: PASS\nREASON: yes"))
    finally:
        set_active_context(None)
    assert len(ctx.verdicts) == 1
    assert ctx.verdicts[0]["criterion"] == "Is it polite?"
    assert ctx.verdicts[0]["passed"] is True


def test_golden_files_roundtrip(tmp_path, monkeypatch):
    import promptgold.golden as golden

    monkeypatch.setattr(golden, "GOLDEN_DIR", tmp_path / "golden")
    nodeid = "tests/test_x.py::test_thing"
    assert golden.load(nodeid) is None
    payload = {"model": "m", "verdicts": [{"criterion": "c", "passed": True}], "responses": ["r"]}
    golden.save(nodeid, payload)
    assert golden.load(nodeid) == payload
