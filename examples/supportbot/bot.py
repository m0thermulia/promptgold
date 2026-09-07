"""SupportBot: the tiny demo app promptgold tests run against.

A "bot" is just a system prompt + a model call. The app code is deliberately
boring — the interesting part is the tests, which is the whole point.
"""

from __future__ import annotations

from pathlib import Path

PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text().strip()


def chat(llm, user_message: str) -> str:
    """Send a customer message to Sabun and get its reply."""
    return llm.complete(system=load_system_prompt(), user=user_message)
