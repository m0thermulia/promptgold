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

# Live CassetteModels by (nodeid, model spec). Lets judge() wrap its own
# model into the SAME per-test cassette, so judge calls replay offline too.
_REGISTRY: dict[tuple[str, str], CassetteModel] = {}


def get_or_create(inner: Any, nodeid: str) -> CassetteModel:
    """Return the shared cassette wrapper for `nodeid` + inner.spec."""
    key = (nodeid, inner.spec)
    if key not in _REGISTRY:
        _REGISTRY[key] = CassetteModel(inner, nodeid)
    return _REGISTRY[key]


def save_all(nodeid: str) -> list[Path]:
    """Flush every cassette recorded for this test (bot model + judge model)."""
    saved = []
    for (nid, _spec), cassette in list(_REGISTRY.items()):
        if nid == nodeid:
            if path := cassette.save():
                saved.append(path)
    return saved


def clear(nodeid: str) -> None:
    """Drop registry entries for a test once it has finished."""
    for key in [k for k in _REGISTRY if k[0] == nodeid]:
        del _REGISTRY[key]


def _slug(nodeid: str, model_spec: str = "") -> str:
    """Cassette filename.

    Includes the model spec when set: a test may record into two models (the
    one under test and an independent judge), and without the spec in the
    name the second model's save() overwrites the first's responses.
    """
    base = re.sub(r"[^A-Za-z0-9_.-]+", "_", nodeid)
    if model_spec:
        base += "__" + re.sub(r"[^A-Za-z0-9_.-]+", "_", model_spec)
    return base + ".json"


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
        self.path = CASSETTE_DIR / _slug(nodeid, self.spec)
        self._data: dict[str, Any] = {"model": self.spec, "responses": {}}
        # Fall back to the pre-0.2.1 filename (no model spec) so cassettes
        # committed before that release still replay instead of silently
        # falling through to the live API and charging the user.
        legacy = CASSETTE_DIR / _slug(nodeid)
        if self.path.exists():
            self._data = json.loads(self.path.read_text())
        elif legacy.exists():
            self._data = json.loads(legacy.read_text())
            self._legacy_path = legacy
        else:
            self._legacy_path = None
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
