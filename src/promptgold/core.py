"""Core decorator and LLM test context."""

from __future__ import annotations

import functools
import inspect
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from promptgold.models import Model

# The context of the currently-running prompt test, if any. judge() records
# verdicts here so the plugin can compare them against golden files.
_active_context: LLMContext | None = None


def set_active_context(ctx: LLMContext | None) -> None:
    global _active_context
    _active_context = ctx


def get_active_context() -> LLMContext | None:
    return _active_context


@dataclass
class LLMContext:
    """Passed to every @prompt_test function. Wraps a Model with run metadata."""

    model: Any
    calls: list[dict[str, Any]] = field(default_factory=list)
    verdicts: list[dict[str, Any]] = field(default_factory=list)

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
        sig = inspect.signature(fn)
        params = [p for p in sig.parameters.values() if p.name != "llm"]
        # `llm` becomes a **kwargs catch-all (must be last) so pytest collects
        # fixtures for real params but never resolves `llm` as a fixture.
        params.append(inspect.Parameter("llm", kind=inspect.Parameter.VAR_KEYWORD))

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            llm = kwargs.pop("llm", None)
            if llm is None:
                m = model if isinstance(model, Model) else Model(model, **model_kwargs)
                llm = LLMContext(model=m)
            return fn(llm, *args, **kwargs)

        # Rewrite the visible signature: keep real parameter names so pytest
        # collects fixtures for them, but make `llm` a **kwargs catch-all so
        # pytest never tries to resolve it as a fixture (we inject it ourselves).
        wrapper.__signature__ = sig.replace(parameters=params)  # type: ignore[attr-defined]
        wrapper._promptgold_model = model  # type: ignore[attr-defined]
        wrapper._promptgold_kwargs = model_kwargs  # type: ignore[attr-defined]
        wrapper._is_promptgold_test = True  # type: ignore[attr-defined]
        return wrapper

    return decorator
