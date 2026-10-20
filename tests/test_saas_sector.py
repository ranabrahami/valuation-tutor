"""The SaaS module against the real engine data.

Skipped when the saas-valuation-engine's processed data isn't available.
"""

import math

import pandas as pd
import pytest

saas_valuation = pytest.importorskip("saas_valuation")
from saas_valuation.config import load_config, project_path  # noqa: E402

from valuation_tutor.core.explain import Explainer  # noqa: E402
from valuation_tutor.core.i18n import Translator  # noqa: E402
from valuation_tutor.sectors.saas import SaasSector  # noqa: E402

PROCESSED = project_path(load_config()["data"]["processed_dir"])
pytestmark = pytest.mark.skipif(not (PROCESSED / "comps.csv").exists(), reason="engine data not built")


@pytest.fixture(scope="module")
def sector():
    return SaasSector()


@pytest.fixture(scope="module")
def explainer(sector):
    return Explainer(sector, Translator("en"))


def test_universe_and_dates(sector):
    assert len(sector.companies()) == 18
    assert sector.data_as_of == str(pd.read_csv(PROCESSED / "market_data.csv")["fetched_at"].max())[:10]


def test_numbers_match_the_engine(sector):
    fin = pd.read_csv(PROCESSED / "financials.csv")
    row = fin[(fin.ticker == "HUBS") & (fin.fiscal_year == 2025)].iloc[0]
    data = sector.company_data("HUBS")
    assert data.facts()["HUBS.revenue.FY2025"].value == row["revenue"]
    summary = sector.engine.dcf_summary.loc["HUBS"]
    assert data.valuation.fair_value.value == pytest.approx(summary["implied_price"])
    assert data.valuation.implied_growth.value == pytest.approx(summary["market_implied_growth"])


def test_every_fact_has_a_source_and_no_nan(sector):
    for ref in sector.companies():
        for fact in sector.company_data(ref.ticker).facts().values():
            assert fact.source, fact.id
            assert fact.value is None or math.isfinite(fact.value), fact.id
            if fact.value is None:
                assert fact.note, f"{fact.id} is missing without an explanation"


def test_every_chart_works_for_every_company(sector, explainer):
    for ref in sector.companies():
        data = sector.company_data(ref.ticker)
        for chart_id in explainer.charts:
            e = explainer.explain(data, chart_id)
            assert e.available, (ref.ticker, chart_id)
            assert e.observations and all("{" not in o.text for o in e.observations)


def test_teaching_examples_show_what_they_are_meant_to_teach(sector):
    ex = sector.teaching_examples()
    ddog = sector.company_data(ex["profit_vs_cash"]).history
    assert ddog["operating_income"][-1].value < 0 < ddog["free_cash_flow"][-1].value
    snapshot = {r.ticker: sector.company_data(r.ticker).snapshot for r in sector.companies()}
    ev_rev = {t: s["ev_revenue"].value for t, s in snapshot.items()}
    assert max(ev_rev, key=ev_rev.get) == ex["peers_ev_revenue"]
    sbc = {r.ticker: sector.company_data(r.ticker).history["sbc_pct_revenue"][-1].value for r in sector.companies()}
    assert max(sbc, key=sbc.get) == ex["sbc"]
    crwd = sector.company_data(ex["implied_growth"]).valuation
    assert crwd.implied_growth.value > 2 * crwd.actual_growth.value
    adbe = [f.value for f in sector.company_data(ex["revenue_trend"]).history["revenue"]]
    assert adbe == sorted(adbe)


def test_missing_history_is_explained_not_filled(sector):
    fcf = sector.company_data("VEEV").history["free_cash_flow"]
    gaps = [f for f in fcf if f.missing]
    assert gaps and all("guessed" in f.note for f in gaps)
