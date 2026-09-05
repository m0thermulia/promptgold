"""Core decorator and LLM test context."""

from __future__ import annotations

import functools
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from inspect import Signature
from typing import Any

from promptspec.models import Model


@dataclass
class LLMContext:
    """Passed to every @prompt_test function. Wraps a Model with run metadata."""

    model: Model
    calls: list[dict[str, Any]] = field(default_factory=list)

    def complete(self, system: str = "", user: str = "", **kwargs: Any) -> str:
        start = time.monotonic()
        text = self.model.complete(system=system, user=user, **kwargs)
        self.calls.append(
            {
                "system": system,
                "user": user,
                "response": text,
                "latency_ms": (time.monotonic() - start) * 1000,
            }
        )
        return text

    @property
    def last_response(self) -> str:
        return self.calls[-1]["response"] if self.calls else ""


def prompt_test(model: str | Model, **model_kwargs: Any) -> Callable:
    """Mark a function as a prompt test.

    The decorated function receives an `llm` (LLMContext) argument.
    """

    def decorator(fn: Callable) -> Callable:
        @functools.wraps(fn)
        def wrapper() -> Any:
            m = model if isinstance(model, Model) else Model(model, **model_kwargs)
            return fn(LLMContext(model=m))

        # Hide the original signature from pytest: without this, pytest sees the
        # `llm` parameter (via __wrapped__) and tries to resolve it as a fixture.
        wrapper.__signature__ = Signature()  # type: ignore[attr-defined]
        wrapper._promptspec_model = model  # type: ignore[attr-defined]
        wrapper._promptspec_kwargs = model_kwargs  # type: ignore[attr-defined]
        wrapper._is_promptspec_test = True  # type: ignore[attr-defined]
        return wrapper

    return decorator
