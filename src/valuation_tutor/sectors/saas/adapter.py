"""The only file in this project that imports the saas-valuation-engine.

It loads the engine's processed data, runs the engine's own DCF and ranking
code, and hands back plain tables. module.py turns those into core Facts.
Nothing here re-implements a valuation: the numbers a learner sees are the
numbers the engine (and its Excel outputs) produce.

The one formula repeated here is fiscal-year free cash flow for the history
charts, using the engine's definition (operating cash flow - capex -
capitalized software). The engine only computes it calendarized; exposing a
fiscal version from the engine would remove this duplication.
"""

from __future__ import annotations

import copy
from dataclasses import dataclass
from datetime import date

import numpy as np
import pandas as pd
from saas_valuation.config import load_config, project_path
from saas_valuation.models.comps import prepare_fiscal
from saas_valuation.models.dcf import value_universe
from saas_valuation.models.ranking import build_ranking


@dataclass
class EngineOutput:
    cfg: dict
    history: pd.DataFrame        # one row per company per fiscal year, with derived ratios
    comps: pd.DataFrame          # calendar-year comps, index = ticker
    market: pd.DataFrame
    dcf_summary: pd.DataFrame
    dcf_results: dict            # ticker -> {"projection", "sensitivity", ...}
    regression: dict
    valuation_date: date


def _ratio(num: pd.Series, den: pd.Series) -> pd.Series:
    return (num / den).where(den > 0)


def fiscal_history(financials: pd.DataFrame, subtract_capitalized_software: bool) -> pd.DataFrame:
    fin = prepare_fiscal(financials).sort_values(["ticker", "fiscal_year"])
    software = fin["capitalized_software"] if subtract_capitalized_software else 0.0
    fin["free_cash_flow"] = fin["operating_cash_flow"] - fin["capex"] - software
    fin["gross_margin"] = _ratio(fin["gross_profit_calc"], fin["revenue"])
    fin["operating_margin"] = _ratio(fin["operating_income"], fin["revenue"])
    fin["fcf_margin"] = _ratio(fin["free_cash_flow"], fin["revenue"])
    fin["sbc_pct_revenue"] = _ratio(fin["stock_based_comp"], fin["revenue"])
    # Growth only between consecutive fiscal years of the same company.
    prev = fin.groupby("ticker")[["revenue", "fiscal_year"]].shift(1)
    consecutive = fin["fiscal_year"] - prev["fiscal_year"] == 1
    fin["revenue_growth"] = (fin["revenue"] / prev["revenue"] - 1).where(consecutive)
    return fin


def load_engine(cfg: dict | None = None) -> EngineOutput:
    cfg = copy.deepcopy(cfg or load_config())
    processed = project_path(cfg["data"]["processed_dir"])
    comps, bridge, market = (pd.read_csv(processed / f"{name}.csv", index_col="ticker")
                             for name in ("comps", "ev_bridge", "market_data"))
    financials = pd.read_csv(processed / "financials.csv")

    # Value everything as of the market-data date, not "today": otherwise the
    # engine rolls values forward daily and a lesson's numbers would drift.
    valuation_date = date.fromisoformat(str(market["fetched_at"].max())[:10])
    cfg["dcf"]["valuation_date"] = valuation_date.isoformat()

    summary, results, _, _ = value_universe(comps, bridge, market, cfg)
    ranked = build_ranking(comps, bridge, market, summary, cfg)
    history = fiscal_history(financials, cfg["comps"]["fcf_subtract_capitalized_software"])
    return EngineOutput(cfg=cfg, history=history, comps=comps, market=market, dcf_summary=summary,
                        dcf_results=results, regression=ranked["regression"], valuation_date=valuation_date)


def clean(value) -> float | None:
    """Engine NaN/inf -> None, so core types never carry NaN."""
    if value is None:
        return None
    try:
        v = float(value)
    except (TypeError, ValueError):
        return None
    return None if not np.isfinite(v) else v
