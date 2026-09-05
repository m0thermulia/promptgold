# promptspec

**pytest for prompts.** Write a test, get a baseline, catch regressions in CI.

```python
from promptspec import prompt_test, judge, contains

@prompt_test(model="openai:gpt-4o-mini")
def test_support_stays_empathetic(llm):
    response = llm.complete(
        system="You are a helpful support agent.",
        user="your product is garbage and I want my money back",
    )
    assert not contains(response, "calm down")
    assert judge(response, "Is this response empathetic?") >= 4
```

```bash
$ pytest
test_support_stays_empathetic PASSED (1.2s, $0.0003)

$ pytest --baseline
# first run records golden outputs

$ pytest
test_support_stays_empathetic REGRESSED
  judge score: 4 → 2
  baseline: "I completely understand your frustration..."
  current:  "I apologize, but our policy states..."
```

That's it. Five concepts. No YAML. No platform. No account.

## Why promptspec

You changed a system prompt. Did it break anything? Today the answer is "vibes" — you eyeball a few outputs and ship it. promptspec makes prompt changes testable like code changes:

- **pytest-native** — prompt tests live next to your unit tests, run with `pytest`, fail in CI
- **Baselines** — first run records outputs; later runs diff against them automatically
- **LLM-as-judge** — score subjective quality ("empathetic?", "correct?") without writing rubrics
- **Multi-provider** — OpenAI, Anthropic, Ollama. One `Model` class, swap with a string
- **Zero cloud** — local SQLite history, works offline with Ollama, no signups

## What promptspec is NOT

Opinionated rejection is a feature. promptspec deliberately has:

- ❌ No dashboard or web UI
- ❌ No hosted tier, no accounts, no telemetry
- ❌ No 50-metric zoo — three assertions cover 90% of cases
- ❌ No YAML-first config — tests are Python code, versioned with your code

If you need a full eval platform, use [DeepEval](https://github.com/confident-ai/deepeval) or [LangSmith](https://langsmith.com). If you need Node-based matrix testing, use [Promptfoo](https://promptfoo.dev). If you want to add prompt tests in 10 minutes, you're in the right place.

## Install

```bash
pip install promptspec
export OPENAI_API_KEY=...   # or ANTHROPIC_API_KEY, or run Ollama locally
```

## The five concepts

### 1. `@prompt_test`

Decorator marking a function as a prompt test. Discovered by the pytest plugin.

```python
@prompt_test(model="anthropic:claude-sonnet-4-5")
def test_refund_policy(llm): ...
```

### 2. Assertions

Three cover almost everything:

```python
contains(response, "refund")              # substring / regex
matches(response, r"order #\d+")          # regex
judge(response, "Is the answer correct?") # LLM-graded 1-5, returns int
```

### 3. Baselines

```bash
pytest --baseline          # record current outputs as golden
pytest                     # diff against golden, fail on regression
```

### 4. `Model`

```python
Model("openai:gpt-4o-mini")
Model("anthropic:claude-sonnet-4-5")
Model("ollama:llama3.1")          # fully offline
```

### 5. Exit codes

Non-zero on any failure or regression. CI just works — GitHub Actions, GitLab, whatever.

## Roadmap

- [x] v0.1 — core: decorator, 3 assertions, baselines, 3 providers, pytest plugin
- [ ] v0.2 — snapshot diff viewer, cost tracking, JUnit XML
- [ ] v0.3 — flaky test detection (run N times, report variance)
- [ ] v0.4 — adversarial test pack (jailbreak / injection / PII)

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues are labeled. Be kind, ship small PRs.

## License

MIT
