"""Shared fixtures: a stubbed Model so prompt tests run offline."""

from __future__ import annotations

import pytest

import promptgold.models


@pytest.fixture
def stub_model(monkeypatch):
    """Replace Model's network calls with canned responses.

    Detects judge calls (system prompt asks for VERDICT) and returns a passing
    verdict; otherwise returns the canned response. Yields a callable to change
    the canned response mid-test.
    """
    state = {"response": "I understand your frustration, happy to help with a refund."}

    def fake_init(self, spec, **kw):
        self.provider, self.name = spec.split(":", 1)
        self.spec = spec
        self.temperature, self.max_tokens, self.extra = 0.0, 100, kw

    def fake_complete(self, system="", user="", **kw):
        if "VERDICT" in system:
            return "VERDICT: PASS\nREASON: stub judge approves"
        return state["response"]

    monkeypatch.setattr(promptgold.models.Model, "__init__", fake_init)
    monkeypatch.setattr(promptgold.models.Model, "complete", fake_complete)

    def set_response(text: str) -> None:
        state["response"] = text

    return set_response
