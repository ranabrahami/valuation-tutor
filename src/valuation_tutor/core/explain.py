"""Put the three explanation layers together for one chart of one company.

This is what the UI shows under each chart, and (from milestone 3) what the
tutor receives as context: the reading guide, the sector's notes, the
company-specific observations, the terms used and every Fact on the chart.
"""

from __future__ import annotations

from dataclasses import dataclass

import altair as alt

from .charts import KINDS, ChartContext, Guide, Observation
from .concepts import all_concepts
from .fmt import Formatter
from .i18n import Translator
from .sector import ChartDef, CompanyData, Concept, Fact, SectorModule


@dataclass
class ExplainedChart:
    chart: ChartDef
    available: bool
    figure: alt.Chart | None
    guide: Guide
    sector_notes: tuple[str, ...]
    observations: list[Observation]
    terms: list[Concept]
    facts: list[Fact]


class Explainer:
    """Builds ExplainedCharts for one sector in one locale."""

    def __init__(self, sector: SectorModule, t: Translator):
        self.sector, self.t = sector, t
        self.fmt = Formatter(sector.currency, t)
        self.metrics = {m.id: m for m in sector.metrics()}
        self.concepts = all_concepts(t, sector.concepts())
        self.charts = {c.id: c for c in sector.charts()}
        unknown = {c.kind for c in self.charts.values()} - set(KINDS)
        if unknown:
            raise ValueError(f"Sector {sector.id!r} uses unknown chart kinds: {sorted(unknown)}")

    def context(self, data: CompanyData, chart: ChartDef) -> ChartContext:
        return ChartContext(data=data, chart=chart, metrics=self.metrics, fmt=self.fmt, t=self.t)

    def explain(self, data: CompanyData, chart_id: str) -> ExplainedChart:
        chart = self.charts[chart_id]
        kind = KINDS[chart.kind]
        ctx = self.context(data, chart)
        ok = kind.available(ctx)
        return ExplainedChart(
            chart=chart, available=ok,
            figure=kind.render(ctx) if ok else None,
            guide=kind.guide(ctx),
            sector_notes=chart.sector_notes,
            observations=kind.observations(ctx) if ok else [],
            terms=[self.concepts[c] for c in chart.concepts if c in self.concepts],
            facts=kind.facts_used(ctx) if ok else [],
        )
