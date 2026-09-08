"""Provider-agnostic Model class. One string, any provider."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from promptgold.pricing import estimate_tokens


def _parse_json_lenient(text: str) -> dict[str, Any]:
    """Parse the FIRST JSON object in `text`, ignoring trailing garbage.

    Real-world OpenAI-compatible endpoints sometimes append extra bytes
    after a valid completion object (proxy banners, JSONL tails, duplicated
    braces). The openai SDK's strict parser dies on these with
    'Extra data'; we only need the first object, so use raw_decode and
    discard whatever follows.
    """
    stripped = text.lstrip()
    try:
        obj, _end = json.JSONDecoder().raw_decode(stripped)
    except json.JSONDecodeError as e:
        raise ValueError(
            f"Endpoint returned unparseable response ({type(e).__name__}): {text[:200]!r}"
        ) from e
    if not isinstance(obj, dict):
        raise ValueError(f"Endpoint returned a non-object JSON value: {type(obj).__name__}")
    return obj


class Model:
    """Unified chat-completion interface.

    Spec format: "provider:model_name"
      Model("openai:gpt-4o-mini")
      Model("anthropic:claude-sonnet-4-5")
      Model("ollama:llama3.1")
    """

    def __init__(self, spec: str, temperature: float = 0.0, max_tokens: int = 1024, **kw: Any):
        if ":" not in spec:
            raise ValueError(
                f"Model spec must be 'provider:name', got {spec!r}. "
                f"Did you mean 'openai:{spec}'? Providers: openai, anthropic, ollama. "
                "(For OpenAI-compatible endpoints use 'openai:<model>' plus OPENAI_BASE_URL.)"
            )
        self.provider, self.name = spec.split(":", 1)
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.extra = kw
        self.spec = spec
        # Filled by the most recent complete() call: {"input": int, "output": int}
        self.last_usage: dict[str, int] | None = None

    def complete(self, system: str = "", user: str = "", **kwargs: Any) -> str:
        handler = getattr(self, f"_{self.provider}", None)
        if handler is None:
            raise ValueError(
                f"Unknown provider {self.provider!r}. Supported: openai, anthropic, ollama"
            )
        return handler(system=system, user=user, **{**self.extra, **kwargs})

    # --- providers -------------------------------------------------------

    def _openai(self, system: str, user: str, **kw: Any) -> str:
        """Chat completion via the OpenAI protocol — spoken directly over httpx.

        We deliberately do NOT use the openai SDK here: its strict response
        parser rejects the malformed-but-recoverable JSON some OpenAI-
        compatible endpoints return (trailing bytes after the completion
        object). One POST plus lenient parsing covers the whole protocol we
        need and works with OpenAI, openagentic, and any compatible gateway.
        """
        base = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        api_key = os.environ.get("OPENAI_API_KEY", "")
        if not api_key:
            raise ValueError(
                "OPENAI_API_KEY is not set. For OpenAI-compatible endpoints also "
                "set OPENAI_BASE_URL (e.g. https://your-provider/api/v1)."
            )

        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        payload: dict[str, Any] = {
            "model": self.name,
            "messages": messages,
            "temperature": kw.pop("temperature", self.temperature),
            "max_tokens": kw.pop("max_tokens", self.max_tokens),
            **kw,
        }
        r = httpx.post(
            base.rstrip("/") + "/chat/completions",
            json=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
            timeout=120,
        )
        if r.status_code >= 400:
            raise RuntimeError(
                f"OpenAI-compatible endpoint error {r.status_code}: {r.text[:300]}"
            )
        data = _parse_json_lenient(r.text)

        usage = data.get("usage")
        if isinstance(usage, dict) and "prompt_tokens" in usage:
            self.last_usage = {
                "input": usage["prompt_tokens"],
                "output": usage.get("completion_tokens", 0),
            }
        else:
            self.last_usage = None

        choices = data.get("choices") or []
        if not choices:
            raise ValueError(f"Endpoint returned no choices: {r.text[:200]!r}")
        return choices[0].get("message", {}).get("content") or ""

    def _anthropic(self, system: str, user: str, **kw: Any) -> str:
        import anthropic

        client = anthropic.Anthropic()
        resp = client.messages.create(
            model=self.name,
            system=system or anthropic.NOT_GIVEN,
            messages=[{"role": "user", "content": user}],
            temperature=kw.pop("temperature", self.temperature),
            max_tokens=kw.pop("max_tokens", self.max_tokens),
            **kw,
        )
        self.last_usage = {
            "input": resp.usage.input_tokens,
            "output": resp.usage.output_tokens,
        }
        return "".join(b.text for b in resp.content if b.type == "text")

    def _ollama(self, system: str, user: str, **kw: Any) -> str:
        base = os.environ.get("OLLAMA_HOST", "http://localhost:11434")
        payload: dict[str, Any] = {
            "model": self.name,
            "prompt": f"{system}\n\n{user}".strip(),
            "stream": False,
            "options": {"temperature": kw.pop("temperature", self.temperature)},
        }
        r = httpx.post(f"{base}/api/generate", json=payload, timeout=120)
        r.raise_for_status()
        data = r.json()
        text = data.get("response", json.dumps(data))
        self.last_usage = {
            "input": data.get("prompt_eval_count", estimate_tokens(system + user)),
            "output": data.get("eval_count", estimate_tokens(text)),
        }
        return text
