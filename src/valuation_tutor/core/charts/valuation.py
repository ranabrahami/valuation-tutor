"""Charts of a DCF valuation: price vs value, what the price implies, sensitivity.

These never say "buy" or "sell". A gap between price and model value is shown
as a question to investigate, because the model's assumptions are exactly what
the learner is here to question.
"""

from __future__ import annotations

import altair as alt
import pandas as pd

from ..sector import Fact
from . import style
from .base import ChartContext, ChartKind, Observation


def _bar_pair(ctx: ChartContext, rows: list[tuple[str, Fact, str]]) -> alt.Chart:
    """Two labelled horizontal bars; colour says which is the subject."""
    df = pd.DataFrame([{"label": label, "value": f.value, "shown": ctx.fmt.fact(f), "color": color,
                        "source": f.source} for label, f, color in rows if not f.missing])
    order = [label for label, _, _ in rows]
    base = alt.Chart(df).encode(y=alt.Y("label:N", sort=order, title=None, axis=alt.Axis(labelLimit=260)))
    bars = base.mark_bar(cornerRadiusEnd=4, height=34).encode(
        x=alt.X("value:Q", title=None, axis=alt.Axis(labels=False, ticks=False, grid=False)),
        color=alt.Color("color:N", scale=None),
        tooltip=[alt.Tooltip("label:N", title=" "), alt.Tooltip("shown:N", title=ctx.t.t("chart_ui.value")),
                 alt.Tooltip("source:N", title=ctx.t.t("chart_ui.source"))])
    text = base.mark_text(align="left", dx=8, fontSize=15, fontWeight="bold", color=style.INK).encode(
        x="value:Q", text="shown:N")
    return style.finish(alt.layer(bars, text), height=130)


class PriceVsValueChart(ChartKind):
    kind = "price_vs_value"

    def available(self, ctx: ChartContext) -> bool:
        v = ctx.data.valuation
        return v is not None and not v.price.missing

    def facts_used(self, ctx: ChartContext) -> list[Fact]:
        v = ctx.data.valuation
        return [v.price, v.fair_value, v.discount_rate, v.terminal_growth, v.terminal_share]

    def render(self, ctx: ChartContext) -> alt.Chart:
        v = ctx.data.valuation
        return _bar_pair(ctx, [(ctx.t.t("chart_ui.price_today"), v.price, style.CONTEXT),
                               (ctx.t.t("chart_ui.model_value"), v.fair_value, style.FOCUS)])

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt, v = ctx.t, ctx.fmt, ctx.data.valuation
        obs: list[Observation] = []
        if v.fair_value.missing:
            obs.append(Observation(t.t("obs.value.negative", company=ctx.company, note=v.fair_value.note),
                                   (v.fair_value.id,), "warning"))
        else:
            gap = v.fair_value.value / v.price.value - 1
            key = "obs.value.above" if gap > 0.1 else "obs.value.below" if gap < -0.1 else "obs.value.close"
            obs.append(Observation(t.t(key, company=ctx.company, value=fmt.fact(v.fair_value),
                                       price=fmt.fact(v.price), gap=fmt.pct(abs(gap))),
                                   (v.fair_value.id, v.price.id)))
        if not v.terminal_share.missing:
            obs.append(Observation(t.t("obs.value.terminal_share", share=fmt.fact(v.terminal_share)),
                                   (v.terminal_share.id,)))
        obs.append(Observation(t.t("obs.value.caution")))
        return obs


class ImpliedGrowthChart(ChartKind):
    """Reverse DCF: the growth today's price assumes vs the growth the company delivered."""

    kind = "implied_growth"

    def available(self, ctx: ChartContext) -> bool:
        v = ctx.data.valuation
        return v is not None and not v.actual_growth.missing

    def facts_used(self, ctx: ChartContext) -> list[Fact]:
        v = ctx.data.valuation
        return [v.implied_growth, v.actual_growth, v.price]

    def render(self, ctx: ChartContext) -> alt.Chart:
        v = ctx.data.valuation
        return _bar_pair(ctx, [(ctx.t.t("chart_ui.growth_implied"), v.implied_growth, style.FOCUS),
                               (ctx.t.t("chart_ui.growth_actual"), v.actual_growth, style.CONTEXT)])

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt, v = ctx.t, ctx.fmt, ctx.data.valuation
        if v.implied_growth.missing:
            return [Observation(t.t("obs.implied.out_of_range", company=ctx.company,
                                    actual=fmt.fact(v.actual_growth), note=v.implied_growth.note),
                                (v.actual_growth.id,), "warning")]
        implied, actual = v.implied_growth.value, v.actual_growth.value
        params = dict(company=ctx.company, implied=fmt.fact(v.implied_growth), actual=fmt.fact(v.actual_growth),
                      price=fmt.fact(v.price))
        key = ("obs.implied.much_higher" if implied > actual * 1.5 + 0.02 else
               "obs.implied.lower" if implied < actual - 0.03 else "obs.implied.similar")
        return [Observation(t.t("obs.implied.statement", **params),
                            (v.implied_growth.id, v.actual_growth.id, v.price.id)),
                Observation(t.t(key, **params), (v.implied_growth.id, v.actual_growth.id))]


class SensitivityChart(ChartKind):
    """Value per share for a grid of discount rates and terminal growth rates."""

    kind = "sensitivity"

    def available(self, ctx: ChartContext) -> bool:
        return ctx.data.valuation is not None

    def _cell_id(self, ctx: ChartContext, rate: float, growth: float) -> str:
        return f"{ctx.data.ref.ticker}.sensitivity.r{rate * 100:.1f}.g{growth * 100:.1f}"

    def derived_facts(self, ctx: ChartContext) -> list[Fact]:
        s = ctx.data.valuation.sensitivity
        return [Fact(self._cell_id(ctx, r, g),
                     ctx.t.t("chart_ui.sensitivity_cell", rate=ctx.fmt.pct(r, decimals=1), growth=ctx.fmt.pct(g, decimals=1)),
                     s.values[i][j], "per_share", "", s.source)
                for i, r in enumerate(s.rates) for j, g in enumerate(s.growths)]

    def facts_used(self, ctx: ChartContext) -> list[Fact]:
        v = ctx.data.valuation
        return [v.price, v.discount_rate, v.terminal_growth] + self.derived_facts(ctx)

    def render(self, ctx: ChartContext) -> alt.Chart:
        v = ctx.data.valuation
        s, price = v.sensitivity, v.price.value
        rows = []
        for i, r in enumerate(s.rates):
            for j, g in enumerate(s.growths):
                val = s.values[i][j]
                rows.append({"rate": ctx.fmt.pct(r, decimals=1), "growth": ctx.fmt.pct(g, decimals=1), "value": val,
                             "shown": ctx.fmt.per_share(val),
                             "vs_price": None if val is None else max(-0.5, min(0.5, val / price - 1)),
                             "is_base": abs(r - s.base_rate) < 1e-9 and abs(g - s.base_growth) < 1e-9})
        df = pd.DataFrame(rows)
        x = alt.X("growth:N", title=s.growth_label, sort=[ctx.fmt.pct(g, decimals=1) for g in s.growths],
                  axis=alt.Axis(orient="top", labelAngle=0))
        y = alt.Y("rate:N", title=s.rate_label, sort=[ctx.fmt.pct(r, decimals=1) for r in s.rates])
        cells = alt.Chart(df).mark_rect(stroke=style.SURFACE, strokeWidth=2, cornerRadius=3).encode(
            x=x, y=y,
            color=alt.Color("vs_price:Q", legend=None,
                            scale=alt.Scale(domain=[-0.5, 0, 0.5], range=[style.BELOW, style.NEUTRAL, style.ABOVE])),
            tooltip=[alt.Tooltip("rate:N", title=s.rate_label), alt.Tooltip("growth:N", title=s.growth_label),
                     alt.Tooltip("shown:N", title=ctx.t.t("chart_ui.value"))])
        base = alt.Chart(df[df["is_base"]]).mark_rect(fill=None, stroke=style.INK, strokeWidth=2.5,
                                                      cornerRadius=3).encode(x=x, y=y)
        text = alt.Chart(df).transform_filter("!datum.is_base").mark_text(fontSize=13, color=style.INK).encode(
            x=x, y=y, text="shown:N")
        base_text = alt.Chart(df).transform_filter("datum.is_base").mark_text(
            fontSize=13, fontWeight="bold", color=style.INK).encode(x=x, y=y, text="shown:N")
        return style.finish(alt.layer(cells, base, text, base_text), height=260)

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt = ctx.t, ctx.fmt
        v = ctx.data.valuation
        s, price = v.sensitivity, v.price.value
        cells = {(i, j): s.values[i][j] for i in range(len(s.rates)) for j in range(len(s.growths))}
        known = {k: val for k, val in cells.items() if val is not None}
        bi = min(range(len(s.rates)), key=lambda i: abs(s.rates[i] - s.base_rate))
        bj = min(range(len(s.growths)), key=lambda j: abs(s.growths[j] - s.base_growth))
        base = cells[(bi, bj)]
        ids = {k: self._cell_id(ctx, s.rates[k[0]], s.growths[k[1]]) for k in cells}
        obs: list[Observation] = []
        if base is not None:
            obs.append(Observation(t.t("obs.sensitivity.base", value=fmt.per_share(base),
                                       rate=fmt.pct(s.base_rate, decimals=1), growth=fmt.pct(s.base_growth, decimals=1)),
                                   (ids[(bi, bj)], v.discount_rate.id, v.terminal_growth.id)))
        if known:
            lo, hi = min(known, key=known.get), max(known, key=known.get)
            obs.append(Observation(t.t("obs.sensitivity.range", low=fmt.per_share(known[lo]),
                                       high=fmt.per_share(known[hi])), (ids[lo], ids[hi])))
            above = sum(val > price for val in known.values())
            obs.append(Observation(t.t("obs.sensitivity.above_price", count=above, total=len(cells),
                                       price=fmt.fact(v.price)), (v.price.id,)))
        if base is not None and bi + 1 < len(s.rates) and cells[(bi + 1, bj)] is not None:
            higher = cells[(bi + 1, bj)]
            obs.append(Observation(t.t("obs.sensitivity.rate_step",
                                       points=f"{(s.rates[bi + 1] - s.rates[bi]) * 100:g}",
                                       change=fmt.pct(higher / base - 1, signed=True)),
                                   (ids[(bi, bj)], ids[(bi + 1, bj)])))
        return obs
