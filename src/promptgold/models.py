"""Provider-agnostic Model class. One string, any provider."""

from __future__ import annotations

import json
import os
from typing import Any

import httpx

from promptgold.pricing import estimate_tokens


class Model:
    """Unified chat-completion interface.

    Spec format: "provider:model_name"
      Model("openai:gpt-4o-mini")
      Model("anthropic:claude-sonnet-4-5")
      Model("ollama:llama3.1")
    """

    def __init__(self, spec: str, temperature: float = 0.0, max_tokens: int = 1024, **kw: Any):
        if ":" not in spec:
            raise ValueError(f"Model spec must be 'provider:name', got {spec!r}")
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
        import openai

        client = openai.OpenAI()
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": user})
        resp = client.chat.completions.create(
            model=self.name,
            messages=messages,
            temperature=kw.pop("temperature", self.temperature),
            max_tokens=kw.pop("max_tokens", self.max_tokens),
            **kw,
        )
        if resp.usage is not None:
            self.last_usage = {
                "input": resp.usage.prompt_tokens,
                "output": resp.usage.completion_tokens,
            }
        else:
            self.last_usage = None
        return resp.choices[0].message.content or ""

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
