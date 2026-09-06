"""Tests for cost tracking — pricing table, usage capture, LLMContext totals."""

from __future__ import annotations

import pytest

from promptgold import pricing
from promptgold.core import LLMContext
from promptgold.models import Model


class UsageStubModel:
    """Model-shaped stub that reports token usage like a real provider."""

    def __init__(self, spec: str, input_tokens: int = 100, output_tokens: int = 50):
        self.spec = spec
        self.provider, self.name = spec.split(":", 1)
        self.last_usage = {"input": input_tokens, "output": output_tokens}

    def complete(self, system: str = "", user: str = "", **kwargs) -> str:
        return "ok"


def test_known_model_price():
    assert pricing.price_for("openai:gpt-4o-mini") == (0.15, 0.60)


def test_unknown_model_price_is_none():
    assert pricing.price_for("openai:made-up-model-9000") is None


def test_ollama_is_free():
    assert pricing.cost("ollama:llama3.1", 1000, 1000) == 0.0


def test_cost_math():
    # gpt-4o-mini: $0.15/1M input, $0.60/1M output
    c = pricing.cost("openai:gpt-4o-mini", 1_000_000, 1_000_000)
    assert c == pytest.approx(0.75)


def test_price_override_env(monkeypatch):
    monkeypatch.setenv(
        "PROMPTGOLD_PRICE_OVERRIDES", '{"openai:gpt-4o-mini": [1.0, 2.0]}'
    )
    assert pricing.price_for("openai:gpt-4o-mini") == (1.0, 2.0)
    # malformed override is ignored, not fatal
    monkeypatch.setenv("PROMPTGOLD_PRICE_OVERRIDES", "{not json")
    assert pricing.price_for("openai:gpt-4o-mini") == (0.15, 0.60)


def test_estimate_tokens():
    assert pricing.estimate_tokens("") == 1
    assert pricing.estimate_tokens("a" * 400) == 100


def test_context_tracks_cost_per_call():
    ctx = LLMContext(model=UsageStubModel("openai:gpt-4o-mini", 1000, 500))
    ctx.complete(user="hi")
    call = ctx.calls[0]
    assert call["usage"] == {"input": 1000, "output": 500}
    expected = (1000 * 0.15 + 500 * 0.60) / 1_000_000
    assert call["cost_usd"] == pytest.approx(expected)
    assert ctx.total_cost == pytest.approx(expected)


def test_context_total_cost_sums_calls():
    ctx = LLMContext(model=UsageStubModel("openai:gpt-4o-mini", 1000, 500))
    ctx.complete(user="one")
    ctx.complete(user="two")
    single = (1000 * 0.15 + 500 * 0.60) / 1_000_000
    assert ctx.total_cost == pytest.approx(2 * single)


def test_context_cost_none_for_unknown_model():
    ctx = LLMContext(model=UsageStubModel("openai:unknown-model"))
    ctx.complete(user="hi")
    assert ctx.calls[0]["cost_usd"] is None
    assert ctx.total_cost is None


def test_real_model_has_last_usage_slot():
    m = Model("openai:gpt-4o-mini")
    assert m.last_usage is None
