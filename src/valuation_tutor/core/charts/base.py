"""What every chart kind provides: a picture, a reading guide and observations.

A chart kind is generic ("a metric over time", "one company against its peers").
A sector picks kinds and fills their roles with its own metrics (ChartDef), so
the same reading guide teaches "revenue over time" for a software company and
"sales over time" for a supermarket.

Three explanation layers, from general to specific:
  1. guide()         how to read this kind of chart (core, written once)
  2. sector notes    what's normal in this sector (ChartDef.sector_notes)
  3. observations()  what this company's chart shows, computed from its Facts
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Literal

import altair as alt

from ..fmt import Formatter
from ..i18n import Translator
from ..sector import ChartDef, CompanyData, Fact, MetricDef

Tone = Literal["neutral", "good", "warning"]


@dataclass(frozen=True)
class Observation:
    """One plain-language sentence about this company's chart.

    text is already translated and formatted; facts lists the ids of every
    number in it, so the learner (and the tutor) can see where it came from.
    """

    text: str
    facts: tuple[str, ...] = ()
    tone: Tone = "neutral"


@dataclass(frozen=True)
class Guide:
    """How to read this chart, for someone who has never seen one."""

    axes: str
    look_first: str
    good: str
    worrying: str


@dataclass
class ChartContext:
    data: CompanyData
    chart: ChartDef
    metrics: dict[str, MetricDef]
    fmt: Formatter
    t: Translator
    extra: dict = field(default_factory=dict)

    def metric(self, role: str) -> MetricDef | None:
        metric_id = self.chart.roles.get(role)
        return self.metrics.get(metric_id) if metric_id else None

    def label(self, role: str) -> str:
        m = self.metric(role)
        return m.label if m else ""

    def series(self, role: str) -> list[Fact]:
        metric_id = self.chart.roles.get(role)
        return self.data.history.get(metric_id, []) if metric_id else []

    @property
    def company(self) -> str:
        return self.data.ref.name


class ChartKind(ABC):
    kind: str
    roles_required: tuple[str, ...] = ()
    roles_optional: tuple[str, ...] = ()

    def guide(self, ctx: ChartContext) -> Guide:
        labels = {role: ctx.label(role) for role in (*self.roles_required, *self.roles_optional)}
        key = f"charts.{self.kind}"
        variant = self.guide_variant(ctx)
        prefix = f"{key}.{variant}" if variant else key
        return Guide(*(ctx.t.t(f"{prefix}.{part}", company=ctx.company, **labels)
                       for part in ("axes", "look_first", "good", "worrying")))

    def guide_variant(self, ctx: ChartContext) -> str:
        """Override to pick a guide sub-key, e.g. when an optional role is absent."""
        return ""

    def available(self, ctx: ChartContext) -> bool:
        """False when this company lacks the data to draw the chart at all."""
        return True

    @abstractmethod
    def render(self, ctx: ChartContext) -> alt.Chart: ...

    @abstractmethod
    def observations(self, ctx: ChartContext) -> list[Observation]: ...

    def facts_used(self, ctx: ChartContext) -> list[Fact]:
        """Every Fact drawn on the chart; shown as the chart's sources."""
        return [f for role in self.chart_roles(ctx) for f in ctx.series(role)] + self.derived_facts(ctx)

    def derived_facts(self, ctx: ChartContext) -> list[Fact]:
        """Numbers the chart itself calculates (e.g. a point on a fitted line).

        They are Facts too, with a source saying how they were derived, so the
        tutor can cite them and the grounding check can verify them.
        """
        return []

    def chart_roles(self, ctx: ChartContext) -> list[str]:
        return [r for r in (*self.roles_required, *self.roles_optional) if r in ctx.chart.roles]
