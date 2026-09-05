"""pytest plugin: discovers @prompt_test functions, handles baselines."""

from __future__ import annotations

from typing import Any

import pytest

from promptspec.baselines import BaselineStore, test_id_for
from promptspec.core import LLMContext
from promptspec.models import Model


def pytest_addoption(parser: pytest.Parser) -> None:
    group = parser.getgroup("promptspec")
    group.addoption(
        "--baseline",
        action="store_true",
        default=False,
        help="Record current prompt outputs as the golden baseline.",
    )
    group.addoption(
        "--no-baseline-check",
        action="store_true",
        default=False,
        help="Run prompt tests without comparing against baselines.",
    )


@pytest.fixture(scope="session")
def promptspec_store() -> BaselineStore:
    store = BaselineStore()
    yield store
    store.close()


class BaselineMismatch(AssertionError):
    pass


@pytest.hookimpl(tryfirst=True)
def pytest_runtest_call(item: pytest.Item) -> None:
    """Wrap promptspec tests with baseline recording/comparison."""
    fn = getattr(item, "obj", None)
    if fn is None or not getattr(fn, "_is_promptspec_test", False):
        return

    store = item._promptspec_store  # injected in pytest_runtest_setup
    tid = test_id_for(item.nodeid, str(fn._promptspec_model))

    # Rebuild context so we can capture calls
    model_spec = fn._promptspec_model
    model = model_spec if isinstance(model_spec, Model) else Model(model_spec)
    ctx = LLMContext(model=model)

    # Call original unwrapped function with our context
    original = fn.__wrapped__
    original(ctx)

    payload: dict[str, Any] = {
        "model": model.spec,
        "responses": [c["response"] for c in ctx.calls],
        "latency_ms": sum(c["latency_ms"] for c in ctx.calls),
    }
    store.record_run(tid, payload)

    if item.config.getoption("--baseline"):
        store.set(tid, payload)
        return

    if item.config.getoption("--no-baseline-check"):
        return

    baseline = store.get(tid)
    if baseline is None:
        # No baseline yet: pass silently, record nothing (explicit --baseline to bless)
        return

    if baseline["responses"] != payload["responses"]:
        diff = _format_diff(baseline, payload)
        raise BaselineMismatch(f"Prompt output regressed vs baseline:\n{diff}")


def pytest_runtest_setup(item: pytest.Item) -> None:
    if getattr(getattr(item, "obj", None), "_is_promptspec_test", False):
        # Session-scoped store via fixture cache hack: create per-session once
        if not hasattr(item.session, "_promptspec_store"):
            item.session._promptspec_store = BaselineStore()  # type: ignore[attr-defined]
        item._promptspec_store = item.session._promptspec_store  # type: ignore[attr-defined]


def pytest_sessionfinish(session: pytest.Session) -> None:
    store = getattr(session, "_promptspec_store", None)
    if store is not None:
        store.close()


def _format_diff(baseline: dict[str, Any], current: dict[str, Any]) -> str:
    lines = []
    for i, (old, new) in enumerate(
        zip(baseline["responses"], current["responses"], strict=False)
    ):
        if old != new:
            lines.append(f"  call {i}:")
            lines.append(f"    baseline: {old[:200]!r}")
            lines.append(f"    current:  {new[:200]!r}")
    return "\n".join(lines) or "  (responses differ in length)"


def pytest_configure(config: pytest.Config) -> None:
    config.addinivalue_line(
        "markers", "promptspec: mark a test as a prompt regression test"
    )
