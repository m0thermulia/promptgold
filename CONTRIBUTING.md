# Contributing to promptspec

Thanks for your interest! promptspec is deliberately tiny — five concepts, minimal API surface. Keep it that way.

## Ground rules

1. **Simplicity is the feature.** If a PR adds a concept a user must learn, it needs strong justification.
2. **No cloud dependencies.** Everything must work offline (Ollama) and without accounts.
3. **Tests run offline.** Unit tests must not require API keys — use stubs (see `tests/test_core.py`).
4. **Small PRs.** One feature or fix per PR.

## Dev setup

```bash
git clone https://github.com/rsubundamulia/promptspec
cd promptspec
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
pytest tests/          # offline unit tests
ruff check src tests   # lint
```

## Running prompt tests locally

```bash
export OPENAI_API_KEY=...
pytest examples/ --baseline   # bless current outputs
pytest examples/              # diff against baseline
```

## Good first issues

Look for the `good first issue` label on GitHub. Docs improvements and new assertion helpers are great starting points.
