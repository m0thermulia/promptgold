"""Baseline storage: SQLite-backed golden outputs and run history."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

DEFAULT_DB = Path(".promptspec/history.db")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS baselines (
    test_id TEXT PRIMARY KEY,
    payload TEXT NOT NULL,
    updated_at REAL NOT NULL
);
CREATE TABLE IF NOT EXISTS runs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    test_id TEXT NOT NULL,
    payload TEXT NOT NULL,
    ran_at REAL NOT NULL
);
"""


def test_id_for(nodeid: str, model_spec: str) -> str:
    return hashlib.sha256(f"{nodeid}|{model_spec}".encode()).hexdigest()[:16]


class BaselineStore:
    def __init__(self, db_path: Path = DEFAULT_DB):
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = sqlite3.connect(db_path)
        self.db.executescript(_SCHEMA)

    def get(self, test_id: str) -> dict[str, Any] | None:
        row = self.db.execute(
            "SELECT payload FROM baselines WHERE test_id = ?", (test_id,)
        ).fetchone()
        return json.loads(row[0]) if row else None

    def set(self, test_id: str, payload: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT OR REPLACE INTO baselines (test_id, payload, updated_at) VALUES (?, ?, ?)",
            (test_id, json.dumps(payload), time.time()),
        )
        self.db.commit()

    def record_run(self, test_id: str, payload: dict[str, Any]) -> None:
        self.db.execute(
            "INSERT INTO runs (test_id, payload, ran_at) VALUES (?, ?, ?)",
            (test_id, json.dumps(payload), time.time()),
        )
        self.db.commit()

    def close(self) -> None:
        self.db.close()
