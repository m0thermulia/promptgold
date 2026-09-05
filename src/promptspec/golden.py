"""Golden files: plain-text expected verdicts, committed to your repo.

Why files and not a database: CI runners start clean. A SQLite blob in a
local folder is gone on every CI run, un-reviewable in PRs, and un-diffable.
Golden files live in version control next to your tests — reviewable,
diffable, and present in CI. GitHub is the diff viewer.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

GOLDEN_DIR = Path(".promptspec/golden")


def golden_path(nodeid: str) -> Path:
    """Map a pytest nodeid to its golden file path.

    tests/test_prompts.py::test_empathy -> .promptspec/golden/test_prompts__test_empathy.json
    """
    safe = nodeid.replace("/", "_").replace("::", "__").replace(".py", "")
    return GOLDEN_DIR / f"{safe}.json"


def load(nodeid: str) -> dict[str, Any] | None:
    p = golden_path(nodeid)
    if not p.exists():
        return None
    return json.loads(p.read_text())


def save(nodeid: str, payload: dict[str, Any]) -> Path:
    p = golden_path(nodeid)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(payload, indent=2) + "\n")
    return p
