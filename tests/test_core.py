"""Unit tests for promptspec core — run offline with a stub provider."""

from __future__ import annotations

import re

import pytest

from promptspec import Model, contains, matches, prompt_test
from promptspec.models import Model as ModelClass


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

    assert getattr(my_test, "_is_promptspec_test", False)
    assert my_test._promptspec_model == "stub:stub"


def test_llm_context_records_calls():
    from promptspec.core import LLMContext

    ctx = LLMContext(model=StubModel("canned"))
    out = ctx.complete(system="s", user="u")
    assert out == "canned"
    assert len(ctx.calls) == 1
    assert ctx.calls[0]["response"] == "canned"
    assert ctx.last_response == "canned"


def test_judge_with_stub_model():
    from promptspec.assertions import judge

    score = judge("anything", "Is it good?", model=StubModel("4"))
    assert score == 4


def test_judge_rejects_bad_output():
    from promptspec.assertions import judge

    with pytest.raises(ValueError, match="non-score"):
        judge("anything", "Is it good?", model=StubModel("no digits here"))


def test_baseline_store_roundtrip(tmp_path):
    from promptspec.baselines import BaselineStore

    store = BaselineStore(tmp_path / "h.db")
    assert store.get("t1") is None
    store.set("t1", {"responses": ["a"]})
    assert store.get("t1") == {"responses": ["a"]}
    store.record_run("t1", {"responses": ["b"]})
    store.close()
