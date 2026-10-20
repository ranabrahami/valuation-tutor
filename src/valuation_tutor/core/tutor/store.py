"""Where the tutor keeps shared replies and usage, behind one small interface.

core/storage.py's SQLStore implements it on SQLite (local) and Postgres
(deployed); MemoryStore is for unit tests. Usage is logged per learner per
day, so the caps hold however many browser tabs someone opens.
"""

from __future__ import annotations

from datetime import date
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
        self.learners: dict[str, dict] = {}

    def load_learner(self, learner_id):
        return self.learners.get(learner_id)

    def save_learner(self, learner_id, data):
        self.learners[learner_id] = data

    def delete_learner(self, learner_id):
        self.learners.pop(learner_id, None)

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
