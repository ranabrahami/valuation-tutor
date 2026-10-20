"""The SaaS sector: 18 US-listed software companies from the saas-valuation-engine.

Structure (which metrics, which charts, which concepts) is defined here;
the words are in locales/<locale>.yaml; the numbers come from adapter.py.
"""

from __future__ import annotations

from functools import cached_property
from pathlib import Path

import pandas as pd
import yaml

from ...core.sector import (ChartDef, CompanyData, CompanyRef, Concept, Fact, MetricDef, Note, PathChange,
                            PeerFit, ProjectionRow, SensitivityGrid, Unit, Valuation)
from .adapter import EngineOutput, clean, load_engine

LOCALES = Path(__file__).parent / "locales"

# metric id -> (unit, concept it teaches, whether higher is better)
METRICS: dict[str, tuple[Unit, str, str]] = {
    "revenue": ("money", "revenue", "better"),
    "revenue_growth": ("pct", "growth", "better"),
    "gross_margin": ("pct", "gross_margin", "better"),
    "operating_margin": ("pct", "operating_margin", "better"),
    "operating_income": ("money", "profit", "better"),
    "free_cash_flow": ("money", "free_cash_flow", "better"),
    "sbc_pct_revenue": ("pct", "saas.sbc", "worse"),
    "price": ("per_share", "share_price", "neutral"),
    "market_cap": ("money", "market_cap", "neutral"),
    "enterprise_value": ("money", "enterprise_value", "neutral"),
    "ev_revenue": ("multiple", "multiple", "neutral"),
    "ev_ebitda": ("multiple", "multiple", "neutral"),
    "revenue_growth_cy": ("pct", "growth", "better"),
    "fcf_margin_cy": ("pct", "free_cash_flow", "better"),
    "dcf_value": ("per_share", "dcf", "neutral"),
    "implied_growth": ("pct", "implied_expectations", "neutral"),
    "discount_rate": ("pct", "discount_rate", "neutral"),
    "terminal_growth": ("pct", "terminal_value", "neutral"),
    "terminal_share": ("pct", "terminal_value", "neutral"),
    "dcf_revenue": ("money", "dcf", "neutral"),
    "dcf_cash_flow": ("money", "dcf", "neutral"),
}

# Fiscal-year history shown in the "business story" charts.
HISTORY = ("revenue", "revenue_growth", "gross_margin", "operating_margin", "operating_income",
           "free_cash_flow", "sbc_pct_revenue")
DERIVED = {"revenue_growth", "gross_margin", "operating_margin", "free_cash_flow", "sbc_pct_revenue"}

# Calendar-year snapshot used for peer comparisons: metric id -> engine comps column.
SNAPSHOT = {"price": "price", "market_cap": "market_cap", "enterprise_value": "enterprise_value",
            "ev_revenue": "ev_revenue", "ev_ebitda": "ev_ebitda", "revenue_growth_cy": "revenue_growth",
            "fcf_margin_cy": "fcf_margin"}

# chart id -> (core chart kind, roles, concepts it introduces)
CHARTS: dict[str, tuple[str, dict[str, str], tuple[str, ...]]] = {
    "revenue_trend": ("trend", {"bar": "revenue", "growth": "revenue_growth"}, ("revenue", "growth", "fiscal_year")),
    "margins": ("margins", {"first": "gross_margin", "second": "operating_margin"},
                ("margin", "gross_margin", "operating_margin")),
    "profit_vs_cash": ("profit_vs_cash", {"profit": "operating_income", "cash": "free_cash_flow"},
                       ("profit", "free_cash_flow")),
    "sbc": ("margins", {"first": "sbc_pct_revenue"}, ("saas.sbc",)),
    "peers_ev_revenue": ("peers", {"value": "ev_revenue"}, ("multiple", "enterprise_value", "peer_group", "median")),
    "peer_fit": ("peer_fit", {"value": "ev_revenue", "x": "revenue_growth_cy"},
                 ("multiple", "growth", "saas.growth_premium")),
    "price_vs_value": ("price_vs_value", {}, ("share_price", "dcf")),
    "implied_growth": ("implied_growth", {}, ("implied_expectations",)),
    "sensitivity": ("sensitivity", {}, ("sensitivity", "discount_rate", "terminal_value")),
}

# sector concept (without the "saas." prefix) -> prerequisites
CONCEPTS = {
    "subscription": ("revenue",),
    "sbc": ("operating_margin", "free_cash_flow"),
    "rule_of_40": ("growth", "free_cash_flow"),
    "growth_premium": ("multiple", "growth"),
}

# Which company teaches each idea best (checked against the data in tests).
TEACHING_EXAMPLES = {
    "default": "HUBS",
    "revenue_trend": "ADBE",        # large, steady grower
    "growth": "HUBS",               # growth slowing as it scales
    "margins": "VEEV",              # high, stable margins
    "profit_vs_cash": "DDOG",       # small accounting profit, lots of cash
    "sbc": "SNOW",                  # heavy stock-based pay
    "peers_ev_revenue": "CRWD",     # most expensive in the group
    "peer_fit": "HUBS",             # well below the growth line
    "price_vs_value": "WDAY",
    "implied_growth": "CRWD",       # price needs far faster growth than today
    "sensitivity": "WDAY",
}


def _load_content(locale: str) -> dict:
    path = LOCALES / f"{locale}.yaml"
    with open(path if path.exists() else LOCALES / "en.yaml", encoding="utf-8") as f:
        return yaml.safe_load(f)


class SaasSector:
    id = "saas"
    currency = "USD"
    accounting_standard = "US GAAP"

    def __init__(self, locale: str = "en", engine: EngineOutput | None = None):
        self.locale = locale
        self.content = _load_content(locale)
        self._engine = engine
        self.name = self.content["name"]

    @cached_property
    def engine(self) -> EngineOutput:
        return self._engine or load_engine()

    @property
    def data_as_of(self) -> str:
        return self.engine.valuation_date.isoformat()

    # -- structure -------------------------------------------------------------

    def metrics(self) -> list[MetricDef]:
        text = self.content["metrics"]
        return [MetricDef(id=mid, label=text[mid]["label"], unit=unit, definition=text[mid]["definition"],
                          formula=text[mid].get("formula", ""), concept=concept, higher_is=higher)
                for mid, (unit, concept, higher) in METRICS.items()]

    def charts(self) -> list[ChartDef]:
        text = self.content["charts"]
        return [ChartDef(id=cid, kind=kind, title=text[cid]["title"], roles=roles, concepts=concepts,
                         sector_notes=tuple(text[cid].get("notes", ())))
                for cid, (kind, roles, concepts) in CHARTS.items()]

    def concepts(self) -> list[Concept]:
        text = self.content["concepts"]
        return [Concept(id=f"saas.{cid}", name=text[cid]["name"], plain=text[cid]["plain"],
                        analogy=text[cid].get("analogy", ""),
                        prerequisites=tuple(f"saas.{p}" if p in CONCEPTS else p for p in prereqs),
                        sector=self.id)
                for cid, prereqs in CONCEPTS.items()]

    def path_changes(self) -> list[PathChange]:
        return []   # milestone 2

    def teaching_examples(self) -> dict[str, str]:
        return dict(TEACHING_EXAMPLES)

    def headline_metrics(self) -> list[str]:
        return ["revenue", "revenue_growth", "free_cash_flow", "price"]

    def accounting_notes(self) -> list[Note]:
        return [Note(id=nid, title=n["title"], text=n["text"])
                for nid, n in self.content["accounting_notes"].items()]

    # -- data ------------------------------------------------------------------

    def companies(self) -> list[CompanyRef]:
        comps = self.engine.comps
        return [self._ref(t) for t in comps.sort_values("name").index]

    def _ref(self, ticker: str) -> CompanyRef:
        row = self.engine.comps.loc[ticker]
        return CompanyRef(ticker=ticker, name=self._short_name(row["name"]), profile=row["bucket"],
                          profile_label=self.content["profiles"].get(row["bucket"], row["bucket"]))

    @staticmethod
    def _short_name(name: str) -> str:
        """'CrowdStrike Holdings, Inc.' -> 'CrowdStrike': learners read names many times per page."""
        suffixes = (",", " Inc.", " Corporation", " Holdings", " Holding", " Systems", " Communications",
                    " Software")
        changed = True
        while changed:
            changed = False
            for suffix in suffixes:
                if name.endswith(suffix) and len(name) > len(suffix) + 2:
                    name, changed = name[: -len(suffix)], True
        return name

    def _label(self, metric: str) -> str:
        return self.content["metrics"][metric]["label"]

    def _fact(self, ticker: str, metric: str, period: str, value, source: str, note: str = "") -> Fact:
        v = clean(value)
        return Fact(id=f"{ticker}.{metric}.{period}", label=self._label(metric), value=v,
                    unit=METRICS[metric][0], period=period, source=source, note=note if v is None else "")

    def _history(self, ticker: str, name: str) -> dict[str, list[Fact]]:
        src, rows = self.content["sources"], self.engine.history[self.engine.history["ticker"] == ticker]
        out: dict[str, list[Fact]] = {}
        for metric in HISTORY:
            facts = []
            for _, row in rows.iterrows():
                if metric == "revenue_growth" and pd.isna(row[metric]):
                    continue   # no prior year to compare with: not missing, just not defined
                period = f"FY{int(row['fiscal_year'])}"
                formula = self.content["metrics"][metric].get("formula", "")
                source = (src["annual_derived"].format(name=name, period_end=row["period_end"], formula=formula)
                          if metric in DERIVED else src["annual"].format(name=name, period_end=row["period_end"]))
                note = self.content["missing"].get(metric, self.content["missing"]["generic"])
                facts.append(self._fact(ticker, metric, period, row[metric], source, note))
            out[metric] = facts
        return out

    def _snapshot(self, ticker: str) -> dict[str, Fact]:
        e, src = self.engine, self.content["sources"]
        row, year, date = e.comps.loc[ticker], e.cfg["comps"]["calendar_year"], self.data_as_of
        name = self._short_name(row["name"])
        out = {}
        for metric, col in SNAPSHOT.items():
            if metric in ("price", "market_cap"):
                period, source = f"as of {date}", src["market"].format(date=date)
            elif metric in ("ev_revenue", "ev_ebitda", "enterprise_value"):
                period = f"CY{year}"
                source = src["multiple"].format(name=name, label=self._label(metric), date=date, year=year)
            else:
                period, source = f"CY{year}", src["calendar"].format(name=name, year=year)
            note = self.content["missing"]["multiple"] if METRICS[metric][0] == "multiple" else ""
            fact = self._fact(ticker, metric, f"CY{year}", row[col], source, note)
            out[metric] = Fact(**{**fact.__dict__, "period": period})   # id keeps CY; label shows date
        return out

    def _valuation(self, ticker: str, snapshot: dict[str, Fact]) -> Valuation:
        e, src, d = self.engine, self.content["sources"], self.engine.cfg["dcf"]
        s, res = e.dcf_summary.loc[ticker], e.dcf_results[ticker]
        name = self._short_name(e.comps.loc[ticker, "name"])
        dcf_src = src["dcf"].format(name=name, date=self.data_as_of)
        miss = self.content["missing"]

        def fact(metric, value, period="", note=""):
            v = clean(value)
            return Fact(id=f"{ticker}.{metric}", label=self._label(metric), value=v, unit=METRICS[metric][0],
                        period=period, source=dcf_src, note=note if v is None else "")

        projection = [ProjectionRow(
            year=f"CY{int(r['year'])}", stage=r["stage"],
            revenue=Fact(f"{ticker}.dcf_revenue.CY{int(r['year'])}", self._label("dcf_revenue"), clean(r["revenue"]),
                         "money", f"CY{int(r['year'])}", dcf_src),
            cash_flow=Fact(f"{ticker}.dcf_cash_flow.CY{int(r['year'])}", self._label("dcf_cash_flow"),
                           clean(r["fcf"]), "money", f"CY{int(r['year'])}", dcf_src))
            for _, r in res["projection"].reset_index().iterrows()]
        grid = res["sensitivity"]
        sensitivity = SensitivityGrid(
            rate_label=self._label("discount_rate"), growth_label=self._label("terminal_growth"),
            rates=[float(r) for r in grid.index], growths=[float(g) for g in grid.columns],
            values=[[clean(grid.iat[i, j]) for j in range(grid.shape[1])] for i in range(grid.shape[0])],
            base_rate=float(s["wacc"]), base_growth=float(d["terminal_growth_rate"]), source=dcf_src)
        actual = snapshot["revenue_growth_cy"]
        return Valuation(
            price=snapshot["price"],
            fair_value=fact("dcf_value", s["implied_price"], f"as of {self.data_as_of}", miss["fair_value"]),
            implied_growth=fact("implied_growth", s["market_implied_growth"], "first forecast year",
                                miss["implied_growth"]),
            actual_growth=actual,
            discount_rate=fact("discount_rate", s["wacc"]),
            terminal_growth=fact("terminal_growth", d["terminal_growth_rate"]),
            terminal_share=fact("terminal_share", s["tv_pct_ev"]),
            projection=projection, sensitivity=sensitivity,
            method_note=" ".join(self.content["charts"]["price_vs_value"]["notes"]))

    def company_data(self, ticker: str) -> CompanyData:
        ref = self._ref(ticker)
        snapshot = self._snapshot(ticker)
        peers = [(self._ref(t), snapshot if t == ticker else self._snapshot(t)) for t in self.engine.comps.index]
        reg, year = self.engine.regression, self.engine.cfg["comps"]["calendar_year"]
        fit = PeerFit(x_metric="revenue_growth_cy", y_metric="ev_revenue", intercept=float(reg["intercept"]),
                      slope=float(reg["slope"]), r_squared=float(reg["r_squared"]), log_y=True,
                      source=self.content["sources"]["regression"].format(n=int(reg["n"]), year=year))
        return CompanyData(ref=ref, history=self._history(ticker, ref.name), snapshot=snapshot, peers=peers,
                           peer_fit=fit if reg.get("regressor") == "revenue_growth" else None,
                           valuation=self._valuation(ticker, snapshot))
