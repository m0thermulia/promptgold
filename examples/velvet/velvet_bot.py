"""VELVET: the bouncer bot at Club Harapan.

The app is 20 lines — the interesting part is the security scan around it.
"""

from __future__ import annotations

import os
from pathlib import Path

PROMPT_FILE = Path(__file__).parent / "system_prompt.txt"

# The models this demo was recorded with — baked in so the committed
# cassettes replay for anyone who clones the repo, no env vars needed.
# Override PROMPTGOLD_DEMO_MODEL / PROMPTGOLD_JUDGE_MODEL to re-record
# against your own endpoint (then --bless).
MODEL = os.environ.get("PROMPTGOLD_DEMO_MODEL", "openai:qwen3.6-plus")
JUDGE = os.environ.get("PROMPTGOLD_JUDGE_MODEL", "openai:glm-5.2")


def load_system_prompt() -> str:
    return PROMPT_FILE.read_text().strip()


def talk(llm, guest_says: str) -> str:
    """Say something to the bouncer, get Velvet's reply."""
    return llm.complete(system=load_system_prompt(), user=guest_says)
