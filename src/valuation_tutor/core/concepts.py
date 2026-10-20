"""Universal concepts: the ideas every sector's lessons build on.

Their ids are shared by all sectors, which is what lets mastery carry over:
a learner who mastered "margin" with software companies has mastered it when
they switch to supermarkets. The words live in the locale files; this module
only defines ids and the order they build on each other.
"""

from __future__ import annotations

from .i18n import Translator
from .sector import Concept

# concept id -> prerequisites (concepts that should be understood first)
CORE_CONCEPTS: dict[str, tuple[str, ...]] = {
    "revenue": (),
    "fiscal_year": (),
    "growth": ("revenue",),
    "margin": ("revenue",),
    "gross_margin": ("margin",),
    "operating_margin": ("margin",),
    "profit": ("revenue",),
    "free_cash_flow": ("profit",),
    "share_price": (),
    "market_cap": ("share_price",),
    "enterprise_value": ("market_cap",),
    "multiple": ("enterprise_value", "revenue"),
    "peer_group": (),
    "median": (),
    "dcf": ("free_cash_flow",),
    "discount_rate": ("dcf",),
    "terminal_value": ("dcf",),
    "sensitivity": ("dcf", "discount_rate"),
    "implied_expectations": ("dcf", "growth"),
}


def core_concepts(t: Translator) -> list[Concept]:
    return [Concept(id=cid, name=t.t(f"concepts.{cid}.name"), plain=t.t(f"concepts.{cid}.plain"),
                    analogy=t.t(f"concepts.{cid}.analogy"), prerequisites=prereqs)
            for cid, prereqs in CORE_CONCEPTS.items()]


def all_concepts(t: Translator, sector_concepts: list[Concept]) -> dict[str, Concept]:
    """Core concepts plus a sector's own; a sector may not redefine a core concept."""
    concepts = {c.id: c for c in core_concepts(t)}
    for c in sector_concepts:
        if c.id in concepts:
            raise ValueError(f"Sector concept {c.id!r} clashes with a core concept; namespace it, "
                             f"e.g. '{c.sector}.{c.id}'")
        missing = [p for p in c.prerequisites if p not in concepts and p not in {s.id for s in sector_concepts}]
        if missing:
            raise ValueError(f"Concept {c.id!r} has unknown prerequisites: {missing}")
        concepts[c.id] = c
    return concepts
