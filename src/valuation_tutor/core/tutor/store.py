"""Where the tutor keeps shared replies and usage, behind one small interface.

SQLite locally and in tests (MemoryStore for unit tests); milestone 4 adds a
Postgres implementation for the deployed app. Usage is logged per learner per
day, so the caps hold however many browser tabs someone opens.
"""

from __future__ import annotations

import json
import sqlite3
import threading
from datetime import date
from pathlib import Path
from typing import Protocol


class TutorStore(Protocol):
    def get(self, key: str) -> dict | None: ...
    def put(self, key: str, value: dict) -> None: ...
    def record(self, learner_id: str, cost_usd: float, day: date | None = None) -> None: ...
    def calls_today(self, learner_id: str, day: date | None = None) -> int: ...
    def spend_today(self, day: date | None = None) -> float: ...


class MemoryStore:
    def __init__(self):
        self.cache: dict[str, dict] = {}
        self.usage: dict[tuple[str, str], tuple[int, float]] = {}

    def get(self, key):
        return self.cache.get(key)

    def put(self, key, value):
        self.cache[key] = value

    def record(self, learner_id, cost_usd, day=None):
        k = ((day or date.today()).isoformat(), learner_id)
        calls, cost = self.usage.get(k, (0, 0.0))
        self.usage[k] = (calls + 1, cost + cost_usd)

    def calls_today(self, learner_id, day=None):
        return self.usage.get(((day or date.today()).isoformat(), learner_id), (0, 0.0))[0]

    def spend_today(self, day=None):
        d = (day or date.today()).isoformat()
        return sum(cost for (day_, _), (_, cost) in self.usage.items() if day_ == d)


class SQLiteStore:
    def __init__(self, path: Path):
        path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(path, check_same_thread=False)
        self._lock = threading.Lock()
        with self._lock, self._db:
            self._db.execute("CREATE TABLE IF NOT EXISTS cache (key TEXT PRIMARY KEY, value TEXT NOT NULL)")
            self._db.execute("CREATE TABLE IF NOT EXISTS usage (day TEXT, learner TEXT, calls INTEGER, "
                             "cost REAL, PRIMARY KEY (day, learner))")

    def get(self, key):
        with self._lock:
            row = self._db.execute("SELECT value FROM cache WHERE key = ?", (key,)).fetchone()
        return json.loads(row[0]) if row else None

    def put(self, key, value):
        with self._lock, self._db:
            self._db.execute("INSERT OR REPLACE INTO cache VALUES (?, ?)", (key, json.dumps(value)))

    def record(self, learner_id, cost_usd, day=None):
        with self._lock, self._db:
            self._db.execute("INSERT INTO usage VALUES (?, ?, 1, ?) ON CONFLICT(day, learner) DO UPDATE SET "
                             "calls = calls + 1, cost = cost + excluded.cost",
                             ((day or date.today()).isoformat(), learner_id, cost_usd))

    def calls_today(self, learner_id, day=None):
        with self._lock:
            row = self._db.execute("SELECT calls FROM usage WHERE day = ? AND learner = ?",
                                   ((day or date.today()).isoformat(), learner_id)).fetchone()
        return row[0] if row else 0

    def spend_today(self, day=None):
        with self._lock:
            row = self._db.execute("SELECT COALESCE(SUM(cost), 0) FROM usage WHERE day = ?",
                                   ((day or date.today()).isoformat(),)).fetchone()
        return float(row[0])
