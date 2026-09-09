"""VELVET: the bouncer bot at Club Harapan.

The app is 20 lines — the interesting part is the security scan around it.
"""

from __future__ import annotations

import os
from pathlib import Path

PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"

# Set PROMPTGOLD_DEMO_MODEL to point at your own endpoint's model, e.g.
#   export PROMPTGOLD_DEMO_MODEL="openai:qwen3.8-max"
MODEL = os.environ.get("PROMPTGOLD_DEMO_MODEL", "openai:gpt-4o-mini")


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text().strip()


def talk(llm, guest_says: str) -> str:
    """Say something to the bouncer, get Velvet's reply."""
    return llm.complete(system=load_system_prompt(), user=guest_says)
