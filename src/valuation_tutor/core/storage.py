"""Everything the app saves, in one database: learner progress, tutor cache, tutor usage.

One implementation for both places the app runs, chosen by a URL:
  sqlite:///data/app.sqlite             locally (the default)
  postgresql+psycopg://...              when deployed (Supabase)

Learners are stored under an opaque key (a salted hash of their sign-in id),
never an email address. Progress is the Learner as JSON, so adding a field to
the learner model needs no migration.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timezone

from sqlalchemy import Column, Float, Integer, MetaData, String, Table, Text, create_engine, func, select

metadata = MetaData()
learners = Table("learners", metadata,
                 Column("id", String(64), primary_key=True),
                 Column("data", Text, nullable=False),
                 Column("updated_at", String(32), nullable=False))
tutor_cache = Table("tutor_cache", metadata,
                    Column("key", String(64), primary_key=True),
                    Column("value", Text, nullable=False))
tutor_usage = Table("tutor_usage", metadata,
                    Column("day", String(10), primary_key=True),
                    Column("learner", String(64), primary_key=True),
                    Column("calls", Integer, nullable=False),
                    Column("cost", Float, nullable=False))


class SQLStore:
    """Progress store and tutor store (implements core.tutor.store.TutorStore)."""

    def __init__(self, url: str):
        self.engine = create_engine(url, pool_pre_ping=True)
        metadata.create_all(self.engine)

    def _upsert(self, table, values: dict, keys: list[str], update: dict):
        if self.engine.dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import insert
        else:
            from sqlalchemy.dialects.sqlite import insert
        stmt = insert(table).values(**values)
        return stmt.on_conflict_do_update(index_elements=keys, set_=update(stmt) if callable(update) else update)

    # -- learner progress -----------------------------------------------------

    def load_learner(self, learner_id: str) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(learners.c.data).where(learners.c.id == learner_id)).first()
        return json.loads(row[0]) if row else None

    def save_learner(self, learner_id: str, data: dict) -> None:
        values = {"id": learner_id, "data": json.dumps(data), "updated_at": datetime.now(timezone.utc).isoformat()}
        with self.engine.begin() as c:
            c.execute(self._upsert(learners, values, ["id"], {"data": values["data"],
                                                             "updated_at": values["updated_at"]}))

    def delete_learner(self, learner_id: str) -> None:
        with self.engine.begin() as c:
            c.execute(learners.delete().where(learners.c.id == learner_id))

    # -- tutor cache ------------------------------------------------------------

    def get(self, key: str) -> dict | None:
        with self.engine.connect() as c:
            row = c.execute(select(tutor_cache.c.value).where(tutor_cache.c.key == key)).first()
        return json.loads(row[0]) if row else None

    def put(self, key: str, value: dict) -> None:
        with self.engine.begin() as c:
            c.execute(self._upsert(tutor_cache, {"key": key, "value": json.dumps(value)}, ["key"],
                                   {"value": json.dumps(value)}))

    # -- tutor usage (caps) -----------------------------------------------------

    def record(self, learner_id: str, cost_usd: float, day: date | None = None) -> None:
        values = {"day": (day or date.today()).isoformat(), "learner": learner_id, "calls": 1, "cost": cost_usd}
        with self.engine.begin() as c:
            c.execute(self._upsert(tutor_usage, values, ["day", "learner"],
                                   lambda stmt: {"calls": tutor_usage.c.calls + 1,
                                                 "cost": tutor_usage.c.cost + stmt.excluded.cost}))

    def calls_today(self, learner_id: str, day: date | None = None) -> int:
        with self.engine.connect() as c:
            row = c.execute(select(tutor_usage.c.calls).where(
                tutor_usage.c.day == (day or date.today()).isoformat(), tutor_usage.c.learner == learner_id)).first()
        return row[0] if row else 0

    def spend_today(self, day: date | None = None) -> float:
        with self.engine.connect() as c:
            total = c.execute(select(func.coalesce(func.sum(tutor_usage.c.cost), 0.0)).where(
                tutor_usage.c.day == (day or date.today()).isoformat())).scalar()
        return float(total)
