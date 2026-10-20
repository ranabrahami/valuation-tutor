"""Charts of one company over time: a metric's trend, margins, profit vs cash."""

from __future__ import annotations

import altair as alt
import pandas as pd

from ..sector import Fact
from . import style
from .base import ChartContext, ChartKind, Observation

# A change in growth or margin smaller than this is described as "steady".
STEADY = 0.03


def present(facts: list[Fact]) -> list[Fact]:
    return [f for f in facts if not f.missing]


def missing_observation(ctx: ChartContext, facts: list[Fact]) -> list[Observation]:
    gaps = [f for f in facts if f.missing]
    if not gaps:
        return []
    note = next((f.note for f in gaps if f.note), "")
    return [Observation(ctx.t.t("obs.missing", label=gaps[0].label,
                                periods=", ".join(f.period for f in gaps), note=note),
                        tuple(f.id for f in gaps), "warning")]


def scaled(ctx: ChartContext, facts: list[Fact]) -> tuple[float, str]:
    """Divisor and axis title, so money axes read "$ billions" instead of 3e9."""
    unit = facts[0].unit if facts else "number"
    if unit == "money":
        return ctx.fmt.money_scale([f.value for f in facts])
    if unit == "pct":
        return 1.0, ""
    return 1.0, facts[0].label if facts else ""


class TrendChart(ChartKind):
    """One metric over time as bars, with the yearly growth written above each bar.

    Growth goes in labels rather than on a second axis: two y-axes on one chart
    is the most common way to confuse a reader.
    """

    kind = "trend"
    roles_required = ("bar",)
    roles_optional = ("growth",)

    def guide_variant(self, ctx: ChartContext) -> str:
        return "" if "growth" in ctx.chart.roles else "plain"

    def available(self, ctx: ChartContext) -> bool:
        return len(present(ctx.series("bar"))) >= 2

    def render(self, ctx: ChartContext) -> alt.Chart:
        bars = ctx.series("bar")
        growth = {f.period: f for f in ctx.series("growth")}
        div, title = scaled(ctx, bars)
        df = pd.DataFrame([{
            "period": f.period,
            "value": None if f.missing else f.value / div,
            "shown": ctx.fmt.fact(f),
            "growth": (ctx.fmt.pct(growth[f.period].value, signed=True)
                       if f.period in growth and not growth[f.period].missing else ""),
            "gap": ctx.t.t("fmt.missing") if f.missing else "",
            "source": f.source,
        } for f in bars])
        x = alt.X("period:N", title=None, sort=None, axis=alt.Axis(labelAngle=0))
        tooltip = [alt.Tooltip("period:N", title=ctx.t.t("chart_ui.period")),
                   alt.Tooltip("shown:N", title=ctx.label("bar"))]
        if "growth" in ctx.chart.roles:
            tooltip.append(alt.Tooltip("growth:N", title=ctx.label("growth")))
        tooltip.append(alt.Tooltip("source:N", title=ctx.t.t("chart_ui.source")))
        base = alt.Chart(df).encode(x=x)
        layers = [
            base.mark_bar(color=style.FOCUS, cornerRadiusEnd=4, size=38).encode(
                y=alt.Y("value:Q", title=title), tooltip=tooltip),
            base.mark_text(dy=-9, color=style.INK_SECONDARY, fontSize=13).encode(
                y="value:Q", text="growth:N"),
            base.transform_filter("datum.gap != ''").mark_text(color=style.MUTED, dy=-8).encode(
                y=alt.datum(0), text="gap:N"),
        ]
        return style.finish(alt.layer(*layers))

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt = ctx.t, ctx.fmt
        bars = ctx.series("bar")
        have = present(bars)
        obs: list[Observation] = []
        if len(have) >= 2:
            first, last = have[0], have[-1]
            obs.append(Observation(
                t.t("obs.trend.range", label=first.label, first=fmt.fact(first), first_period=first.period,
                    last=fmt.fact(last), last_period=last.period),
                (first.id, last.id)))
            if first.value and first.value > 0 and last.value / first.value >= 1.5:
                obs.append(Observation(
                    t.t("obs.trend.multiplied", times=f"{last.value / first.value:.1f}",
                        years=len(have) - 1), (first.id, last.id), "good"))
            falls = [b for a, b in zip(have, have[1:]) if b.value < a.value]
            if falls:
                obs.append(Observation(t.t("obs.trend.fell_in", label=first.label,
                                           periods=", ".join(f.period for f in falls)),
                                       tuple(f.id for f in falls), "warning"))
            else:
                obs.append(Observation(t.t("obs.trend.rose_every_year", label=first.label),
                                       tuple(f.id for f in have), "good"))
        growth = present(ctx.series("growth"))
        if len(growth) >= 2:
            g0, g1 = growth[0], growth[-1]
            if g1.value < g0.value - STEADY:
                key, tone = "obs.trend.growth_slowed", "neutral"
            elif g1.value > g0.value + STEADY:
                key, tone = "obs.trend.growth_sped_up", "good"
            else:
                key, tone = "obs.trend.growth_steady", "neutral"
            obs.append(Observation(t.t(key, first=fmt.fact(g0), first_period=g0.period,
                                       last=fmt.fact(g1), last_period=g1.period), (g0.id, g1.id), tone))
        return obs + missing_observation(ctx, bars)


class MarginsChart(ChartKind):
    """One or two margins over time as lines (percent of revenue)."""

    kind = "margins"
    roles_required = ("first",)
    roles_optional = ("second",)

    def guide_variant(self, ctx: ChartContext) -> str:
        return "" if "second" in ctx.chart.roles else "single"

    def available(self, ctx: ChartContext) -> bool:
        return len(present(ctx.series("first"))) >= 2

    def render(self, ctx: ChartContext) -> alt.Chart:
        roles = self.chart_roles(ctx)
        colors = {"first": style.FOCUS, "second": style.SECOND}
        rows = [{"period": f.period, "series": ctx.label(role), "value": f.value,
                 "shown": ctx.fmt.fact(f), "source": f.source}
                for role in roles for f in present(ctx.series(role))]
        df = pd.DataFrame(rows)
        labels = [ctx.label(r) for r in roles]
        color = alt.Color("series:N", title=None, sort=labels,
                          scale=alt.Scale(domain=labels, range=[colors[r] for r in roles]),
                          legend=alt.Legend(orient="top") if len(roles) > 1 else None)
        base = alt.Chart(df).encode(
            x=alt.X("period:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
            y=alt.Y("value:Q", title=None, axis=alt.Axis(format="%")),
            color=color)
        tooltip = [alt.Tooltip("period:N", title=ctx.t.t("chart_ui.period")),
                   alt.Tooltip("series:N", title=ctx.t.t("chart_ui.measure")),
                   alt.Tooltip("shown:N", title=ctx.t.t("chart_ui.value")),
                   alt.Tooltip("source:N", title=ctx.t.t("chart_ui.source"))]
        last = df.groupby("series").tail(1)
        layers = [
            base.mark_line(strokeWidth=2),
            base.mark_point(filled=True, size=70).encode(tooltip=tooltip),
            alt.Chart(last).mark_text(align="left", dx=8, fontSize=12, color=style.INK_SECONDARY).encode(
                x=alt.X("period:N", sort=None), y="value:Q", text="shown:N"),
        ]
        if (df["value"] < 0).any():
            layers.append(alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=style.MUTED).encode(y="y:Q"))
        return style.finish(alt.layer(*layers))

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt = ctx.t, ctx.fmt
        obs: list[Observation] = []
        latest: dict[str, Fact] = {}
        for role in self.chart_roles(ctx):
            have = present(ctx.series(role))
            if not have:
                continue
            first, last = have[0], have[-1]
            latest[role] = last
            change = last.value - first.value
            key = ("obs.margins.up" if change > STEADY else
                   "obs.margins.down" if change < -STEADY else "obs.margins.flat")
            obs.append(Observation(t.t(key, label=last.label, last=fmt.fact(last), last_period=last.period,
                                       first=fmt.fact(first), first_period=first.period),
                                   (first.id, last.id), "neutral"))
            if last.value < 0:
                obs.append(Observation(t.t("obs.margins.negative", label=last.label, period=last.period),
                                       (last.id,), "warning"))
        if "first" in latest and "second" in latest:
            a, b = latest["first"], latest["second"]

            def per_hundred(v: float) -> str:
                amount = abs(v) * 100
                digits = 1 if amount < 10 and round(amount, 1) != round(amount) else 0
                return f"{'-' if v < 0 else ''}{fmt.symbol}{amount:,.{digits}f}"

            obs.append(Observation(
                t.t("obs.margins.per_hundred", symbol=fmt.symbol, first_label=a.label, first=per_hundred(a.value),
                    second_label=b.label, second=per_hundred(b.value), period=a.period),
                (a.id, b.id)))
        for role in self.chart_roles(ctx):
            obs += missing_observation(ctx, ctx.series(role))
        return obs


class ProfitVsCashChart(ChartKind):
    """Accounting profit and cash generated, side by side for each year."""

    kind = "profit_vs_cash"
    roles_required = ("profit", "cash")

    def available(self, ctx: ChartContext) -> bool:
        return bool(present(ctx.series("profit"))) and bool(present(ctx.series("cash")))

    def render(self, ctx: ChartContext) -> alt.Chart:
        profit, cash = ctx.series("profit"), ctx.series("cash")
        div, title = scaled(ctx, profit + cash)
        labels = [ctx.label("profit"), ctx.label("cash")]
        rows = [{"period": f.period, "series": ctx.label(role), "value": f.value / div,
                 "shown": ctx.fmt.fact(f), "source": f.source}
                for role, facts in (("profit", profit), ("cash", cash)) for f in present(facts)]
        df = pd.DataFrame(rows)
        tooltip = [alt.Tooltip("period:N", title=ctx.t.t("chart_ui.period")),
                   alt.Tooltip("series:N", title=ctx.t.t("chart_ui.measure")),
                   alt.Tooltip("shown:N", title=ctx.t.t("chart_ui.value")),
                   alt.Tooltip("source:N", title=ctx.t.t("chart_ui.source"))]
        bars = alt.Chart(df).mark_bar(cornerRadiusEnd=3, size=18).encode(
            x=alt.X("period:N", title=None, sort=None, axis=alt.Axis(labelAngle=0)),
            xOffset=alt.XOffset("series:N", sort=labels),
            y=alt.Y("value:Q", title=title),
            color=alt.Color("series:N", title=None, sort=labels,
                            scale=alt.Scale(domain=labels, range=[style.SECOND, style.FOCUS])),
            tooltip=tooltip)
        zero = alt.Chart(pd.DataFrame({"y": [0]})).mark_rule(color=style.MUTED).encode(y="y:Q")
        return style.finish(alt.layer(bars, zero))

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt = ctx.t, ctx.fmt
        profit = {f.period: f for f in present(ctx.series("profit"))}
        cash = {f.period: f for f in present(ctx.series("cash"))}
        common = [p for p in profit if p in cash]
        obs: list[Observation] = []
        if common:
            p, c = profit[common[-1]], cash[common[-1]]
            params = dict(period=p.period, profit_label=p.label, profit=fmt.fact(p),
                          cash_label=c.label, cash=fmt.fact(c))
            if p.value < 0 <= c.value:
                key, tone = "obs.profit_cash.loss_but_cash", "neutral"
            elif p.value < 0 and c.value < 0:
                key, tone = "obs.profit_cash.both_negative", "warning"
            elif c.value >= p.value:
                key, tone = "obs.profit_cash.cash_above", "good"
            else:
                key, tone = "obs.profit_cash.cash_below", "warning"
            obs.append(Observation(t.t(key, **params), (p.id, c.id), tone))
            positive_cash = [cash[k] for k in common if cash[k].value > 0]
            if len(positive_cash) == len(common) and len(common) > 1:
                obs.append(Observation(t.t("obs.profit_cash.cash_every_year", cash_label=c.label),
                                       tuple(cash[k].id for k in common), "good"))
        return obs + missing_observation(ctx, ctx.series("cash"))
