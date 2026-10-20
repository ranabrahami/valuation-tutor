"""The core must work for any sector that implements SectorModule.

Runs every chart kind, guide and observation against an invented supermarket
sector (fake_sector.py) and checks that the core never reaches into sectors/.
"""

import ast
import re
from pathlib import Path

import pytest
from fake_sector import FakeSector

from valuation_tutor.core.charts import KINDS
from valuation_tutor.core.concepts import all_concepts
from valuation_tutor.core.explain import Explainer
from valuation_tutor.core.i18n import Translator
from valuation_tutor.core.registry import load_sector
from valuation_tutor.core.sector import SectorModule

CORE = Path(__file__).resolve().parents[1] / "src" / "valuation_tutor" / "core"


@pytest.fixture(scope="module")
def explainer():
    return Explainer(FakeSector(), Translator("en"))


def test_core_never_imports_a_sector():
    for path in CORE.rglob("*.py"):
        tree = ast.parse(path.read_text())
        for node in ast.walk(tree):
            names = ([a.name for a in node.names] if isinstance(node, ast.Import) else
                     [node.module or ""] if isinstance(node, ast.ImportFrom) else [])
            assert not any("sectors" in n or "saas_valuation" in n for n in names), f"{path.name} imports {names}"


def test_core_text_has_no_sector_specific_terms():
    text = (CORE / "locales" / "en.yaml").read_text()
    for term in ("SaaS", "10-K", "EDGAR", "GAAP", "IFRS", "subscription", "XBRL"):
        assert not re.search(rf"\b{re.escape(term)}\b", text), term


def test_fake_sector_satisfies_the_interface():
    assert isinstance(FakeSector(), SectorModule)
    assert load_sector("fake_sector:FakeSector", "en").id == "fake"


def test_every_chart_kind_is_exercised_by_the_fake_sector():
    assert {c.kind for c in FakeSector().charts()} == set(KINDS)


@pytest.mark.parametrize("ticker", ["AAA", "BBB", "CCC"])
def test_every_chart_explains_itself_for_every_company(explainer, ticker):
    data = FakeSector().company_data(ticker)
    known = set(data.facts())
    for chart_id in explainer.charts:
        e = explainer.explain(data, chart_id)
        assert all(part.strip() for part in vars(e.guide).values())
        if not e.available:
            continue
        assert e.figure.to_dict()          # a valid Vega-Lite spec
        assert e.observations
        allowed = known | {f.id for f in e.facts}
        for o in e.observations:
            assert "{" not in o.text, o.text            # no unfilled placeholder
            assert set(o.facts) <= allowed, (chart_id, o.facts)


def test_sector_currency_and_units_flow_through(explainer):
    e = explainer.explain(FakeSector().company_data("AAA"), "sales")
    assert any("₪12.5B" in o.text for o in e.observations)
    assert any("Same-store sales growth" in e.guide.axes for _ in [0])


def test_charts_without_data_are_marked_unavailable(explainer):
    bbb = FakeSector().company_data("BBB")
    assert not explainer.explain(bbb, "value").available       # no valuation for BBB
    assert not explainer.explain(bbb, "fit").available         # this sector has no fitted line
    peers = explainer.explain(bbb, "peers")
    assert peers.available and any(o.tone == "warning" for o in peers.observations)  # BBB's multiple is NM


def test_missing_values_are_reported_not_hidden(explainer):
    e = explainer.explain(FakeSector().company_data("AAA"), "cash")
    assert any("FY2024" in o.text and o.tone == "warning" for o in e.observations)


def test_sector_concepts_extend_core_concepts_without_clashing():
    t = Translator("en")
    concepts = all_concepts(t, FakeSector().concepts())
    assert {"revenue", "growth", "fake.same_store_sales"} <= set(concepts)
    clash = FakeSector().concepts()[0].__class__("growth", "x", "x", sector="fake")
    with pytest.raises(ValueError):
        all_concepts(t, [clash])
