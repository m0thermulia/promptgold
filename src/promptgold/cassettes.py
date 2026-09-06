"""VCR-style response cassettes: record API responses once, replay free forever.

A cassette is a JSON file mapping a hash of (model spec, system, user) to the
recorded response text. If a cassette exists, the real API is never called —
prompt tests run offline and free. Missing entries are recorded on first run.
"""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any

CASSETTE_DIR = Path(".promptgold/cassettes")


def _slug(nodeid: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid) + ".json"


def _key(model_spec: str, system: str, user: str) -> str:
    h = hashlib.sha256()
    for part in (model_spec, system, user):
        h.update(part.encode())
        h.update(b"\x00")
    return h.hexdigest()


class CassetteModel:
    """Wraps a Model: replay recorded responses, record misses to disk."""

    def __init__(self, inner: Any, nodeid: str):
        self._inner = inner
        self.spec = inner.spec
        self.path = CASSETTE_DIR / _slug(nodeid)
        self._data: dict[str, Any] = {"model": self.spec, "responses": {}}
        if self.path.exists():
            self._data = json.loads(self.path.read_text())
        self._dirty = False
        self.recorded = 0  # calls that hit the real API
        self.replayed = 0  # calls served from the cassette

    @property
    def last_usage(self) -> dict[str, int] | None:
        """Token usage of the inner model's last real call (None on replay)."""
        return getattr(self._inner, "last_usage", None)

    def complete(self, system: str = "", user: str = "", **kwargs: Any) -> str:
        key = _key(self.spec, system, user)
        responses = self._data["responses"]
        if key in responses:
            self.replayed += 1
            return responses[key]
        text = self._inner.complete(system=system, user=user, **kwargs)
        responses[key] = text
        self._dirty = True
        self.recorded += 1
        return text

    def save(self) -> Path | None:
        if not self._dirty:
            return None
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(self._data, indent=2) + "\n")
        self._dirty = False
        return self.path
