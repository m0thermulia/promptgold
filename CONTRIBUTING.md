# Contributing to promptgold

Thanks for your interest! promptgold is deliberately tiny — five concepts, minimal API surface. Keep it that way.

## Ground rules

1. **Simplicity is the feature.** If a PR adds a concept a user must learn, it needs strong justification.
2. **No cloud dependencies.** Everything must work offline (Ollama) and without accounts.
3. **Tests run offline.** Unit tests must not require API keys — use stubs (see `tests/test_core.py`).
4. **Small PRs.** One feature or fix per PR.

## Dev setup

```bash
git clone https://github.com/m0thermulia/promptgold
cd promptgold
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

## Development

### Layout

```
src/promptgold/        library code
tests/                 pytest tests for the library itself
examples/              example prompt tests
.promptgold/golden/    blessed judge verdicts (JSON, committed)
.promptgold/cassettes/ recorded API responses (committed)
.github/workflows/     CI
```

### Commands

```bash
./.venv/bin/pytest                 # run the suite
./.venv/bin/pytest --bless         # record verdicts — see the rules below
./.venv/bin/pytest --no-cassette   # force live API calls, costs money
./.venv/bin/ruff check src tests   # lint
```

Always use `./.venv/bin/` explicitly. A stale editable install once caused a phantom e2e
failure by loading old code after a folder rename. If tests fail in a way that makes no
sense, rebuild the venv first.

### Golden files and cassettes

Golden files are the baseline. Overwriting them silently defeats the entire tool, so
`--bless` and `--no-cassette` are human-approval-only operations. Do not edit
`.promptgold/golden/*.json` by hand — they are generated. Cassettes and golden files are
committed on purpose; do not gitignore them.

### Testing conventions

- pytest, not unittest.
- A new feature means new tests in the same commit.
- A feature is done when the suite is green and lint is clean, not before.
- `contains` and `matches` are preferred over `judge` when either would work.

### Judge independence

`judge()` grades with a model set by `PROMPTGOLD_JUDGE_MODEL`, default `openai:gpt-4o-mini`.

The judge must never be the same model as the one under test. A model grading its own
output is not a weaker result, it is an invalid one. Assert this before trusting any
verdict.

Known past bug: `judge(model=llm.model)` with a wrapped model fell through to the default
judge and hit the real API. Watch for that class of silent fallthrough.

### Version state

v0.1.0 is on PyPI. v0.2 features on main: cassettes, cost tracking, JUnit XML. Still open:
the GitHub PR-comment Action. PyPI is behind main.

## Design constraints

These are deliberate rejections, not gaps. If a change would add one of them, raise it in
an issue before building:

- no dashboard or web UI
- no hosted tier, no accounts, no telemetry
- no 50-metric zoo — three assertions cover it
- no YAML-first config; tests are Python

## Good first issues

Look for the `good first issue` label on GitHub. Docs improvements and new assertion
helpers are great starting points.
