"""Cost tracking: per-call token counts and dollar cost.

Pricing is a static table (USD per 1M tokens, input/output). It's honest and
simple: prices change, so the table is dated and users can override any entry
via PROMPTGOLD_PRICE_OVERRIDES='{"openai:gpt-4o-mini": [0.15, 0.60]}'.

Usage counts come from provider responses where available (OpenAI, Anthropic).
Ollama estimates tokens as ~len(text)/4 — fine for a local $0.00 model.
"""

from __future__ import annotations

import json
import os

# USD per 1M tokens: (input, output). Last checked: 2026-09.
PRICES: dict[str, tuple[float, float]] = {
    "openai:gpt-4o": (2.50, 10.00),
    "openai:gpt-4o-mini": (0.15, 0.60),
    "openai:gpt-4.1": (2.00, 8.00),
    "openai:gpt-4.1-mini": (0.40, 1.60),
    "openai:gpt-4.1-nano": (0.10, 0.40),
    "openai:o3": (2.00, 8.00),
    "openai:o4-mini": (1.10, 4.40),
    "anthropic:claude-opus-4-1": (15.00, 75.00),
    "anthropic:claude-sonnet-4-5": (3.00, 15.00),
    "anthropic:claude-haiku-4-5": (1.00, 5.00),
    "ollama:*": (0.0, 0.0),
}


def _overrides() -> dict[str, tuple[float, float]]:
    raw = os.environ.get("PROMPTGOLD_PRICE_OVERRIDES", "")
    if not raw:
        return {}
    try:
        data = json.loads(raw)
        return {k: (float(v[0]), float(v[1])) for k, v in data.items()}
    except (json.JSONDecodeError, TypeError, IndexError, ValueError):
        return {}


def price_for(spec: str) -> tuple[float, float] | None:
    """(input, output) USD per 1M tokens for a model spec, or None if unknown."""
    overrides = _overrides()
    if spec in overrides:
        return overrides[spec]
    if spec in PRICES:
        return PRICES[spec]
    provider = spec.split(":", 1)[0]
    return PRICES.get(f"{provider}:*")


def cost(spec: str, input_tokens: int, output_tokens: int) -> float | None:
    """Dollar cost of one call, or None if the model's price is unknown."""
    p = price_for(spec)
    if p is None:
        return None
    return (input_tokens * p[0] + output_tokens * p[1]) / 1_000_000


def estimate_tokens(text: str) -> int:
    """Rough token estimate (~4 chars/token) when a provider reports nothing."""
    return max(1, len(text) // 4)
