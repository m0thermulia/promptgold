# promptgold

pytest for prompts. Write a test, bless the verdict, catch regressions in CI.

## Layout

```
src/promptgold/        library code
tests/                 pytest tests for the library itself
examples/              example prompt tests
.promptgold/golden/    blessed judge verdicts (JSON, committed)
.promptgold/cassettes/ recorded API responses (committed)
.github/workflows/     CI
```

## Commands

```bash
./.venv/bin/pytest                 # run the suite
./.venv/bin/pytest --bless         # record verdicts, HUMAN APPROVAL ONLY
./.venv/bin/pytest --no-cassette   # force live API calls, costs money
./.venv/bin/ruff check src tests   # lint
```

Always use `./.venv/bin/` explicitly. A stale editable install once caused a phantom e2e failure by loading old code after a folder rename. If tests fail in a way that makes no sense, rebuild the venv first.

## Rules

- Never run `--bless` without the human saying yes in this session. Golden files are the baseline; overwriting them silently defeats the entire tool.
- Never run `--no-cassette` without the human saying yes. It hits real APIs.
- Do not commit or push without the human saying yes.
- Do not edit `.promptgold/golden/*.json` by hand. They are generated.
- Cassettes and golden files are committed on purpose. Do not gitignore them.

## Design constraints

These are deliberate rejections, not gaps. Do not "fix" them:

- no dashboard or web UI
- no hosted tier, no accounts, no telemetry
- no 50-metric zoo, three assertions cover it
- no YAML-first config, tests are Python

If a change would add one of these, raise it before building.

## Judge independence

`judge()` grades with a model set by `PROMPTGOLD_JUDGE_MODEL`, default `openai:gpt-4o-mini`.

The judge must never be the same model as the one under test. A model grading its own output is not a weaker result, it is an invalid one. Assert this before trusting any verdict.

Known past bug: `judge(model=llm.model)` with a wrapped model fell through to the default judge and hit the real API. Watch for that class of silent fallthrough.

## Testing conventions

- pytest, not unittest
- new feature means new tests in the same commit
- a feature is done when the suite is green and lint is clean, not before
- `contains` and `matches` are preferred over `judge` when either would work

## Version state

v0.1.0 is on PyPI. v0.2 features on main: cassettes, cost tracking, JUnit XML. Still open: GitHub PR-comment Action. PyPI is behind main.
