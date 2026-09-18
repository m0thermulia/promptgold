# promptgold

**pytest for prompts.** Write a test, bless the verdict, catch regressions in CI.

![demo: bless → break the prompt → watch the build go red](docs/demo.gif)

```python
from promptgold import prompt_test, judge, contains

@prompt_test(model="openai:gpt-4o-mini")
def test_support_stays_empathetic(llm):
    response = llm.complete(
        system="You are a helpful support agent.",
        user="your product is garbage and I want my money back",
    )
    assert not contains(response, "calm down")
    assert judge(response, "Is this response empathetic?")
```

```bash
$ pytest --bless          # record the judge verdicts as golden files (commit them)
$ pytest                  # later runs fail if a verdict flips PASS -> FAIL
```

That's it. Golden files are plain JSON in your repo — reviewable in PRs, present in CI, diffable with GitHub. No database, no cloud, no account.

> The example above is a **live** prompt test — it calls a real model, so it needs `OPENAI_API_KEY` set. `pytest` on its own runs promptgold's own offline suite; your prompt tests run when you point it at them (`pytest examples/`). Once a test has run, cassettes replay it for free.

## Why promptgold

You changed a system prompt. Did it break anything? Today the answer is "vibes" — you eyeball a few outputs and ship it. promptgold makes prompt changes testable like code changes:

- **pytest-native** — prompt tests live next to your unit tests, run with `pytest`, fail in CI
- **Golden files in your repo** — judge verdicts are blessed to `.promptgold/golden/*.json` and committed. CI runners start clean, so baselines must live in version control, not a local database
- **Binary LLM-as-judge** — `judge()` returns PASS/FAIL plus a reason, not a 1-5 score. Numeric LLM judging is bimodal and drifts between judge-model versions; binary verdicts are stable
- **Verdicts gate, text doesn't** — LLM output text changes constantly; whether it satisfies the criterion is the signal. Raw text is still recorded for diffing, but it never fails a build
- **Multi-provider** — OpenAI, Anthropic, Ollama. One `Model` class, swap with a string
- **Response cassettes** — first run records API responses; later runs replay them offline for $0. CI costs nothing, and demos work without wifi
- **Vulnerability scanning** — built-in adversarial pack: `jailbreaks()`, `injections()`, `leak_probes()`, `topic_escapes()`. Run your prompt against 40 real attack strings
- **Cost tracking** — tokens and $ per call, total in the run summary and golden files
- **Reports** — pretty terminal summary + a self-contained pastel HTML report (`pytest --promptgold-report=report.html`). No dashboard, no server: it's a file
- **Zero cloud** — works offline with Ollama, no signups, no telemetry

## What promptgold is NOT

Opinionated rejection is a feature. promptgold deliberately has:

- ❌ No dashboard or web UI
- ❌ No hosted tier, no accounts, no telemetry — **baselines live in your repo, not our cloud**
- ❌ No 50-metric zoo — three assertions cover 90% of cases
- ❌ No YAML-first config — tests are Python code, versioned with your code

If you need a full eval platform, use [DeepEval](https://github.com/confident-ai/deepeval) or [LangSmith](https://langsmith.com). If you need Node-based matrix testing, use [Promptfoo](https://promptfoo.dev). If you want to add prompt tests in 10 minutes, you're in the right place.

## Install

```bash
pip install promptgold
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
contains(response, "refund")              # substring / regex -> bool
matches(response, r"order #\d+")          # regex -> bool
judge(response, "Is the answer correct?") # LLM-graded -> Verdict (truthy, has .reason)
```

`judge()` returns a `Verdict`: `bool(verdict)` is the PASS/FAIL, `verdict.reason` explains why.

### 3. Golden files

```bash
pytest --bless     # write judge verdicts to .promptgold/golden/*.json — commit them
pytest             # fail if any verdict flips vs the golden file
```

Golden files are plain JSON. Review them in PRs like any snapshot. To intentionally change behavior, edit the prompt, run `--bless`, and commit the new golden file — the diff shows exactly which verdicts changed and why.

### 4. `Model`

```python
Model("openai:gpt-4o-mini")
Model("anthropic:claude-sonnet-4-5")
Model("ollama:llama3.1")          # fully offline
```

**Using a custom or hosted endpoint?** The provider prefix picks the *protocol*, not the vendor. Most gateways (OpenRouter, Together, Groq, DeepSeek, LM Studio, vLLM, openagentic...) speak the OpenAI chat-completions protocol — for those, use `openai:` + the model ID exactly as your provider lists it, and point the SDK at your endpoint:

```bash
export OPENAI_API_KEY="***"                        # your provider's key
export OPENAI_BASE_URL="https://your-provider/api/v1"
```
```python
Model("openai:qwen3.8")        # provider listed "qwen3.8" → add "openai:" prefix
```

How to tell which protocol your endpoint speaks: docs mention "OpenAI-compatible" or `/v1/chat/completions` → `openai:`. Docs mention the Anthropic Messages API → `anthropic:`. Running locally → `ollama:`.

### 5. Exit codes

Non-zero on any failure or verdict regression. CI just works — GitHub Actions, GitLab, whatever.

## The judge model

`judge()` grades with a model. Default: `PROMPTGOLD_JUDGE_MODEL` env var, else `openai:gpt-4o-mini`.

**Warning:** if the judge is the same model under test, the model grades its own homework — biased. Set `PROMPTGOLD_JUDGE_MODEL` to a different model for independence:

```bash
export PROMPTGOLD_JUDGE_MODEL="anthropic:claude-sonnet-4-5"
```

Or per-call: `judge(response, "...", model="anthropic:claude-sonnet-4-5")`.

## Response cassettes (record once, replay free)

Every prompt test runs through a VCR-style cassette in `.promptgold/cassettes/`.
Matching responses replay instantly for free. By default, **missing responses
call the live model and are recorded** — even when a cassette file exists.

For replay-only runs (recommended in CI):

```bash
pytest --offline
```

`--offline` raises `OfflineCassetteMiss` on a missing cassette or response,
without calling the model or recording anything. The error identifies the test,
model, and cassette path. This covers `llm.complete()` and `judge()` within
`@prompt_test`, including an independent judge selected by environment variable
or `model=`. Existing and legacy cassette filenames both replay unchanged.
It is not a network sandbox: direct SDK/HTTP calls or standalone model calls
outside this cassette path are not intercepted.

- Commit matching bot and judge cassettes alongside golden files.
- On a miss, restore the matching cassette or deliberately run without `--offline`
  to record it. **Recording may incur API charges.**
- `pytest --no-cassette` forces live API calls and cannot be combined with `--offline`.
- Without `--offline`, existing record-on-miss behavior is unchanged.

## Roadmap

- [x] v0.1 — decorator, 3 assertions, binary judge, golden files, 3 providers, pytest plugin
- [x] v0.2 — cassettes, cost tracking, JUnit XML, GitHub PR-comment Action
  - cassettes: first run records API responses to `.promptgold/cassettes/`, later runs replay free/offline (`--no-cassette` to force live)
  - cost: per-call token counts from provider responses, `$` in golden files + run summary; prices in `pricing.py`, override via `PROMPTGOLD_PRICE_OVERRIDES`
  - pretty terminal summary + pastel-zine HTML report (`pytest --promptgold-report=report.html`) — self-contained, offline, no server
  - GitHub Action (`action.yml`) posts verdict deltas + cost as a PR comment; `pytest --promptgold-markdown=PATH` writes the comment body
  - adversarial pack (shipped early): `jailbreaks()`, `injections()`, `leak_probes()`, `topic_escapes()` — 40 attack strings
- [x] v0.3 — self-healing prompts + robust OpenAI-compatible provider
  - `promptgold.heal.heal_prompt()`: a model rewrites a leaking prompt given scan failures; attack text travels as quoted data, never instructions. Demo: `examples/velvet/heal.py` (scan → heal → re-scan loop). Healing proposes, humans adopt.
  - direct-httpx OpenAI provider with lenient JSON parsing — survives gateways that append garbage after the completion object (the openai SDK died on these). `openai:` = the protocol, any compatible endpoint via `OPENAI_BASE_URL`.
- [ ] v0.3.x — flaky verdict detection (run N times, report pass rate), datasets/parametrize
- [ ] v0.4 — `promptgold init <prompt-file>` generates candidate test cases

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Good first issues are labeled. Be kind, ship small PRs.

## License

MIT
