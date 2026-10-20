"""The contract between the sector-agnostic core and a sector module.

The core (charts, explanations, learning path, tutor) only ever sees the types
in this file. A sector module turns its own engine's output into these types;
nothing in core/ may import from sectors/.

The key type is Fact: every number shown to a learner, or given to the tutor,
is a Fact with a label, a period and a source. That is what makes "the tutor
never invents a figure" checkable.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal, Protocol, runtime_checkable

# How a value is formatted. "money" uses the sector's currency.
Unit = Literal["money", "pct", "multiple", "per_share", "number"]


@dataclass(frozen=True)
class Fact:
    """One number with everything needed to explain where it came from."""

    id: str                 # unique and stable, e.g. "HUBS.revenue.FY2025"
    label: str              # "Revenue"
    value: float | None     # None when the source doesn't have it
    unit: Unit
    period: str             # "FY2025", "CY2025", "as of 2026-10-18"
    source: str             # "HubSpot 10-K (SEC XBRL), fiscal year ended 2025-12-31"
    note: str = ""          # why a value is missing, or how it was derived

    @property
    def missing(self) -> bool:
        return self.value is None


@dataclass(frozen=True)
class CompanyRef:
    ticker: str
    name: str
    profile: str            # sector-defined group, e.g. "high_growth_unprofitable"
    profile_label: str      # "High growth, unprofitable"


@dataclass(frozen=True)
class MetricDef:
    """A metric as the learner meets it: what it is, how it's calculated, why it matters."""

    id: str                 # "gross_margin"
    label: str              # "Gross margin"
    unit: Unit
    definition: str         # plain-language, one or two sentences
    formula: str = ""       # "Gross profit ÷ revenue"
    concept: str = ""       # concept id this metric teaches, e.g. "margin"
    higher_is: Literal["better", "worse", "neutral"] = "neutral"


@dataclass(frozen=True)
class ChartDef:
    """One chart a sector shows, built from a core chart kind.

    roles maps the slots of the chart kind to the sector's metric ids, e.g.
    {"bar": "revenue", "growth": "revenue_growth"} for the "trend" kind.
    """

    id: str
    kind: str               # a key of core.charts.KINDS
    title: str
    roles: dict[str, str]
    concepts: tuple[str, ...] = ()
    sector_notes: tuple[str, ...] = ()   # what's normal or special in this sector


@dataclass(frozen=True)
class Concept:
    """Something a learner can master. Core concepts have sector=None."""

    id: str                 # "margin" (core) or "saas.sbc" (sector)
    name: str
    plain: str              # explanation for someone who has never heard the term
    analogy: str = ""       # an everyday comparison, used when re-explaining
    prerequisites: tuple[str, ...] = ()
    sector: str | None = None
    # Optional multiple-choice check: {"prompt", "options", "answer" (index), "why"}.
    # Core concepts keep theirs in the core locale; sector concepts supply it here.
    check: dict | None = field(default=None, hash=False, compare=False)


@dataclass(frozen=True)
class Note:
    """Accounting or data context the tutor needs to explain this sector's numbers."""

    id: str
    title: str
    text: str


@dataclass(frozen=True)
class PathChange:
    """How a sector adapts the core learning path (used from milestone 2)."""

    op: Literal["insert_after", "replace", "remove"]
    target: str             # id of the core step
    step: dict = field(default_factory=dict)   # the new step, for insert/replace


@dataclass(frozen=True)
class ProjectionRow:
    year: str
    stage: Literal["actual", "explicit", "fade"]
    revenue: Fact
    cash_flow: Fact


@dataclass(frozen=True)
class SensitivityGrid:
    """Value per share for each (discount rate, terminal growth) pair."""

    rate_label: str
    growth_label: str
    rates: list[float]
    growths: list[float]
    values: list[list[float | None]]   # values[i][j] for rates[i], growths[j]
    base_rate: float
    base_growth: float
    source: str


@dataclass(frozen=True)
class Valuation:
    price: Fact
    fair_value: Fact               # DCF value per share
    implied_growth: Fact           # reverse DCF: growth the price assumes
    actual_growth: Fact
    discount_rate: Fact
    terminal_growth: Fact
    terminal_share: Fact           # share of value from beyond the forecast
    projection: list[ProjectionRow]
    sensitivity: SensitivityGrid
    method_note: str               # one paragraph: what the model assumes


@dataclass(frozen=True)
class PeerFit:
    """A fitted line through the peer group, e.g. ln(multiple) on growth."""

    x_metric: str
    y_metric: str
    intercept: float
    slope: float
    r_squared: float
    log_y: bool
    source: str


@dataclass
class CompanyData:
    ref: CompanyRef
    # metric id -> chronological Facts, e.g. revenue for FY2021..FY2025
    history: dict[str, list[Fact]]
    # metric id -> latest comparable value (multiples, price, CY metrics)
    snapshot: dict[str, Fact]
    # every company in the peer group, including this one
    peers: list[tuple[CompanyRef, dict[str, Fact]]]
    peer_fit: PeerFit | None = None
    valuation: Valuation | None = None

    def headline(self, metric_ids: list[str]) -> list[Fact]:
        """Latest available value of each metric: snapshot first, else most recent history."""
        out = []
        for mid in metric_ids:
            if mid in self.snapshot and not self.snapshot[mid].missing:
                out.append(self.snapshot[mid])
            else:
                latest = [f for f in self.history.get(mid, []) if not f.missing]
                if latest:
                    out.append(latest[-1])
        return out

    def facts(self) -> dict[str, Fact]:
        """Every Fact for this company, by id: what the tutor is allowed to cite."""
        out: dict[str, Fact] = {}
        for series in self.history.values():
            out.update({f.id: f for f in series})
        out.update({f.id: f for f in self.snapshot.values()})
        for _, values in self.peers:
            out.update({f.id: f for f in values.values()})
        if self.valuation:
            v = self.valuation
            for f in (v.price, v.fair_value, v.implied_growth, v.actual_growth,
                      v.discount_rate, v.terminal_growth, v.terminal_share):
                out[f.id] = f
            for row in v.projection:
                out[row.revenue.id], out[row.cash_flow.id] = row.revenue, row.cash_flow
        return out


@runtime_checkable
class SectorModule(Protocol):
    """What a sector must provide. See docs/ADDING_A_SECTOR.md."""

    id: str                     # "saas"
    name: str                   # "US software (SaaS)"
    currency: str               # ISO code: "USD", "ILS"
    accounting_standard: str    # "US GAAP", "IFRS"
    data_as_of: str             # date of the market data, shown to learners

    def companies(self) -> list[CompanyRef]: ...
    def company_data(self, ticker: str) -> CompanyData: ...
    def metrics(self) -> list[MetricDef]: ...
    def charts(self) -> list[ChartDef]: ...
    def concepts(self) -> list[Concept]: ...
    def path_changes(self) -> list[PathChange]: ...
    def teaching_examples(self) -> dict[str, str]: ...   # concept or chart id -> ticker
    def headline_metrics(self) -> list[str]: ...          # 3-4 metric ids for the company header
    def accounting_notes(self) -> list[Note]: ...
