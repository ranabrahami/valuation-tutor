"""The deployed app runs on the snapshot; it must give the same numbers as the engine."""

import pytest

pytest.importorskip("saas_valuation")
from valuation_tutor.sectors.saas import SaasSector  # noqa: E402
from valuation_tutor.sectors.saas.adapter import SNAPSHOT_DIR, data_source, snapshot_manifest  # noqa: E402

pytestmark = pytest.mark.skipif(not (SNAPSHOT_DIR / "config.yaml").exists(), reason="no snapshot exported")


def test_snapshot_is_used_when_forced(monkeypatch):
    monkeypatch.setenv("VALUATION_TUTOR_DATA", "snapshot")
    _, folder, source = data_source()
    assert source == "snapshot" and folder == SNAPSHOT_DIR
    assert snapshot_manifest()["market_data_date"]


def test_snapshot_matches_the_engine(monkeypatch):
    """Same inputs, same numbers. (Differing dates just mean one side was refreshed more recently.)"""
    if data_source()[2] != "engine":
        pytest.skip("engine data not available to compare")
    live_sector = SaasSector()
    if live_sector.data_as_of != snapshot_manifest()["market_data_date"]:
        pytest.skip(f"engine data ({live_sector.data_as_of}) and snapshot "
                    f"({snapshot_manifest()['market_data_date']}) are from different days")
    live = live_sector.company_data("HUBS")
    monkeypatch.setenv("VALUATION_TUTOR_DATA", "snapshot")
    frozen = SaasSector().company_data("HUBS")
    assert frozen.valuation.fair_value.value == pytest.approx(live.valuation.fair_value.value)
    assert frozen.facts()["HUBS.revenue.FY2025"].value == live.facts()["HUBS.revenue.FY2025"].value
