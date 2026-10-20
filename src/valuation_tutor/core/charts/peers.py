"""Charts that place one company among its peers."""

from __future__ import annotations

import math
import statistics

import altair as alt
import pandas as pd

from ..sector import Fact
from . import style
from .base import ChartContext, ChartKind, Observation


def peer_values(ctx: ChartContext, metric_id: str) -> list[tuple[str, str, Fact]]:
    """(ticker, name, fact) for every peer that has the metric, highest first."""
    rows = [(ref.ticker, ref.name, values[metric_id]) for ref, values in ctx.data.peers
            if metric_id in values and not values[metric_id].missing]
    return sorted(rows, key=lambda r: r[2].value, reverse=True)


def company_fact(ctx: ChartContext, metric_id: str) -> Fact | None:
    for ref, values in ctx.data.peers:
        if ref.ticker == ctx.data.ref.ticker:
            return values.get(metric_id)
    return None


class PeersChart(ChartKind):
    """One metric for every company in the peer group; the subject highlighted."""

    kind = "peers"
    roles_required = ("value",)

    def available(self, ctx: ChartContext) -> bool:
        return len(peer_values(ctx, ctx.chart.roles["value"])) >= 3

    def facts_used(self, ctx: ChartContext) -> list[Fact]:
        return [f for _, _, f in peer_values(ctx, ctx.chart.roles["value"])]

    def render(self, ctx: ChartContext) -> alt.Chart:
        rows = peer_values(ctx, ctx.chart.roles["value"])
        me = ctx.data.ref.ticker
        df = pd.DataFrame([{"name": name, "value": f.value, "shown": ctx.fmt.fact(f),
                            "is_me": ticker == me, "source": f.source} for ticker, name, f in rows])
        order = df["name"].tolist()
        median = statistics.median(df["value"])
        base = alt.Chart(df).encode(y=alt.Y("name:N", sort=order, title=None))
        bars = base.mark_bar(cornerRadiusEnd=3, height=14).encode(
            x=alt.X("value:Q", title=ctx.label("value")),
            color=alt.condition("datum.is_me", alt.value(style.FOCUS), alt.value(style.CONTEXT)),
            tooltip=[alt.Tooltip("name:N", title=ctx.t.t("chart_ui.company")),
                     alt.Tooltip("shown:N", title=ctx.label("value")),
                     alt.Tooltip("source:N", title=ctx.t.t("chart_ui.source"))])
        mine = base.transform_filter("datum.is_me").mark_text(align="left", dx=6, fontWeight="bold",
                                                               color=style.INK).encode(x="value:Q", text="shown:N")
        med = pd.DataFrame({"x": [median], "label": [ctx.t.t("chart_ui.median_label",
                                                             value=ctx.fmt.value(median, rows[0][2].unit))]})
        rule = alt.Chart(med).mark_rule(color=style.INK_SECONDARY, strokeDash=[4, 4]).encode(x="x:Q")
        rule_text = alt.Chart(med).mark_text(align="left", dx=4, dy=-6, color=style.INK_SECONDARY,
                                             baseline="bottom").encode(x="x:Q", y=alt.value(0), text="label:N")
        return style.finish(alt.layer(bars, mine, rule, rule_text), height=max(220, 22 * len(df)))

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt = ctx.t, ctx.fmt
        metric_id = ctx.chart.roles["value"]
        rows = peer_values(ctx, metric_id)
        mine = company_fact(ctx, metric_id)
        obs: list[Observation] = []
        if mine is None or mine.missing:
            obs.append(Observation(t.t("obs.peers.missing", company=ctx.company, label=ctx.label("value"),
                                       note=mine.note if mine else ""), (mine.id,) if mine else (), "warning"))
        else:
            rank = next(i for i, (tk, _, _) in enumerate(rows, 1) if tk == ctx.data.ref.ticker)
            median = statistics.median(f.value for _, _, f in rows)
            key = ("obs.peers.rank_top" if rank == 1 else
                   "obs.peers.rank_bottom" if rank == len(rows) else "obs.peers.rank")
            obs.append(Observation(t.t(key, company=ctx.company, value=fmt.fact(mine),
                                       rank=rank, n=len(rows), label=ctx.label("value")), (mine.id,)))
            ratio = mine.value / median if median else math.nan
            key = ("obs.peers.above_median" if ratio > 1.1 else
                   "obs.peers.below_median" if ratio < 0.9 else "obs.peers.near_median")
            obs.append(Observation(t.t(key, company=ctx.company, median=fmt.value(median, mine.unit),
                                       ratio=f"{ratio:.1f}"), (mine.id,)))
        left_out = len(ctx.data.peers) - len(rows)
        if left_out:
            obs.append(Observation(t.t("obs.peers.left_out", count=left_out, label=ctx.label("value"))))
        return obs


class PeerFitChart(ChartKind):
    """Peers plotted against a driver (e.g. growth), with the fitted line.

    Points below the line are cheaper than companies with similar fundamentals.
    """

    kind = "peer_fit"
    roles_required = ("value", "x")

    def _fit(self, ctx: ChartContext):
        fit = ctx.data.peer_fit
        if fit and fit.x_metric == ctx.chart.roles["x"] and fit.y_metric == ctx.chart.roles["value"]:
            return fit
        return None

    def _points(self, ctx: ChartContext) -> list[dict]:
        y_id, x_id = ctx.chart.roles["value"], ctx.chart.roles["x"]
        return [{"ticker": ref.ticker, "name": ref.name, "x": v[x_id].value, "y": v[y_id].value,
                 "x_shown": ctx.fmt.fact(v[x_id]), "y_shown": ctx.fmt.fact(v[y_id]),
                 "is_me": ref.ticker == ctx.data.ref.ticker}
                for ref, v in ctx.data.peers
                if x_id in v and y_id in v and not v[x_id].missing and not v[y_id].missing]

    def _line_value(self, fit, x: float) -> float:
        y = fit.intercept + fit.slope * x
        return math.exp(y) if fit.log_y else y

    def available(self, ctx: ChartContext) -> bool:
        return self._fit(ctx) is not None and len(self._points(ctx)) >= 3

    def derived_facts(self, ctx: ChartContext) -> list[Fact]:
        fit = self._fit(ctx)
        mine = next((p for p in self._points(ctx) if p["is_me"]), None)
        if not fit or not mine:
            return []
        y_metric = ctx.metric("value")
        return [
            Fact(f"{ctx.data.ref.ticker}.{fit.y_metric}.line", ctx.t.t("chart_ui.line_estimate",
                 label=y_metric.label if y_metric else fit.y_metric),
                 self._line_value(fit, mine["x"]), y_metric.unit if y_metric else "number", "",
                 ctx.t.t("chart_ui.line_source", source=fit.source)),
            Fact(f"{ctx.data.ref.ticker}.{fit.y_metric}.r_squared", "R²", fit.r_squared, "pct", "", fit.source),
        ]

    def facts_used(self, ctx: ChartContext) -> list[Fact]:
        y_id, x_id = ctx.chart.roles["value"], ctx.chart.roles["x"]
        facts = [v[k] for _, v in ctx.data.peers for k in (y_id, x_id) if k in v]
        return facts + self.derived_facts(ctx)

    def render(self, ctx: ChartContext) -> alt.Chart:
        fit = self._fit(ctx)
        df = pd.DataFrame(self._points(ctx))
        xs = [df["x"].min() + i * (df["x"].max() - df["x"].min()) / 40 for i in range(41)]
        line = pd.DataFrame({"x": xs, "y": [self._line_value(fit, x) for x in xs]})
        x_metric, y_metric = ctx.metric("x"), ctx.metric("value")
        x_axis = alt.Axis(format="%") if x_metric and x_metric.unit == "pct" else alt.Axis()
        x = alt.X("x:Q", title=ctx.label("x"), axis=x_axis)
        y_scale = alt.Scale(type="log") if fit.log_y else alt.Scale()
        y = alt.Y("y:Q", title=ctx.label("value"), scale=y_scale)
        tooltip = [alt.Tooltip("name:N", title=ctx.t.t("chart_ui.company")),
                   alt.Tooltip("x_shown:N", title=ctx.label("x")),
                   alt.Tooltip("y_shown:N", title=ctx.label("value"))]
        points = alt.Chart(df).mark_circle(stroke=style.SURFACE, strokeWidth=2).encode(
            x=x, y=y, tooltip=tooltip,
            color=alt.condition("datum.is_me", alt.value(style.FOCUS), alt.value(style.CONTEXT)),
            size=alt.condition("datum.is_me", alt.value(220), alt.value(110)))
        labels = alt.Chart(df).transform_filter("!datum.is_me").mark_text(
            align="left", dx=9, fontSize=11, color=style.MUTED).encode(x=x, y=y, text="ticker:N")
        my_label = alt.Chart(df).transform_filter("datum.is_me").mark_text(
            align="left", dx=12, fontSize=13, fontWeight="bold", color=style.INK).encode(x=x, y=y, text="name:N")
        fitted = alt.Chart(line).mark_line(color=style.INK_SECONDARY, strokeDash=[6, 4], strokeWidth=1.5).encode(
            x="x:Q", y=alt.Y("y:Q", scale=y_scale))
        return style.finish(alt.layer(fitted, points, labels, my_label), height=360)

    def observations(self, ctx: ChartContext) -> list[Observation]:
        t, fmt = ctx.t, ctx.fmt
        derived = self.derived_facts(ctx)
        if not derived:
            return [Observation(t.t("obs.peers.missing", company=ctx.company, label=ctx.label("value"),
                                    note=""), (), "warning")]
        line, r2 = derived
        mine = next(p for p in self._points(ctx) if p["is_me"])
        gap = mine["y"] / line.value - 1
        key = ("obs.peer_fit.below_line" if gap < -0.1 else
               "obs.peer_fit.above_line" if gap > 0.1 else "obs.peer_fit.on_line")
        y_fact = company_fact(ctx, ctx.chart.roles["value"])
        x_fact = company_fact(ctx, ctx.chart.roles["x"])
        return [
            Observation(t.t(key, company=ctx.company, x_label=ctx.label("x").lower(), x=mine["x_shown"],
                            line=fmt.fact(line), actual=mine["y_shown"], gap=fmt.pct(abs(gap))),
                        (line.id, y_fact.id, x_fact.id)),
            Observation(t.t("obs.peer_fit.r_squared", r2=fmt.pct(r2.value), x_label=ctx.label("x").lower()),
                        (r2.id,)),
        ]
