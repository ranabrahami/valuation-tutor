"""The AI tutor, with a fake Claude client so nothing is billed."""

import json
from datetime import date
from types import SimpleNamespace

import pytest
from fake_sector import FakeSector

from valuation_tutor.core.explain import Explainer
from valuation_tutor.core.fmt import Formatter
from valuation_tutor.core.i18n import Translator
from valuation_tutor.core.learner import Learner
from valuation_tutor.core.registry import load_settings
from valuation_tutor.core.tutor import Tutor, Unavailable, cost, grounding
from valuation_tutor.core.tutor.context import context_for, sector_block
from valuation_tutor.core.tutor.store import MemoryStore, SQLiteStore

CFG = load_settings()["tutor"]


class FakeClient:
    """Mimics client.messages.create; replies are queued dicts (or "refusal")."""

    def __init__(self, *replies):
        self.replies, self.calls = list(replies), []
        self.messages = SimpleNamespace(create=self._create)

    def _create(self, **body):
        self.calls.append(json.loads(json.dumps(body, default=str)))
        reply = self.replies.pop(0)
        usage = SimpleNamespace(input_tokens=1000, output_tokens=200, cache_read_input_tokens=0,
                                cache_creation_input_tokens=0)
        if reply == "refusal":
            return SimpleNamespace(content=[], stop_reason="refusal", usage=usage)
        return SimpleNamespace(content=[SimpleNamespace(type="thinking", thinking=""),
                                        SimpleNamespace(type="text", text=json.dumps(reply))],
                               stop_reason="end_turn", usage=usage)


@pytest.fixture
def setup():
    sector = FakeSector()
    t = Translator()
    ex = Explainer(sector, t)
    learner = Learner()
    ctx = context_for(ex, sector.company_data("AAA"), "sales", learner, {"title": "Sales"})
    return sector, ex, learner, ctx


def make(client, store=None):
    t = Translator()
    return Tutor(client, CFG, store or MemoryStore(), Formatter("ILS", t))


def sales_fy2024_tag(ctx):
    return next(tag for tag, f in ctx.tags().items() if f.id == "AAA.sales.FY2024")


def test_request_shape_caching_and_rules(setup):
    _, _, _, ctx = setup
    client = FakeClient({"reply": "Look at the bars.", "verdict": "partly", "credit_own_words": True})
    make(client).review_observation(ctx, "sales go up", "learner-1")
    body = client.calls[0]
    assert body["model"] == CFG["model"] and body["output_config"]["effort"] == CFG["effort"]
    assert body["output_config"]["format"]["schema"]["required"] == ["reply", "verdict", "credit_own_words"]
    system, user = body["system"], body["messages"][0]["content"]
    assert "cache_control" in system[1] and "cache_control" in user[0]       # sector + chart blocks cached
    assert "Never recommend buying, selling" in system[0]["text"]
    assert "sales go up" in user[1]["text"]


def test_sector_context_comes_only_from_the_module(setup):
    sector, _, _, ctx = setup
    block = sector_block(sector)
    assert "IFRS" in block and "Store leases are on the balance sheet" in block and "₪" not in "SaaS"
    assert "SaaS" not in block and "GAAP" not in block
    assert "Alef Markets" in ctx.chart_block(Formatter("ILS", Translator()))


def test_fact_sheet_tags_every_number_with_its_source(setup):
    _, _, _, ctx = setup
    sheet = ctx.fact_sheet(Formatter("ILS", Translator()))
    tag = sales_fy2024_tag(ctx)
    assert f"[{tag}] Sales, FY2024: ₪12.5B (source: Invented test data for AAA)" in sheet


def test_grounded_reply_is_accepted_with_its_sources(setup):
    _, _, _, ctx = setup
    tag = sales_fy2024_tag(ctx)
    tutor = make(FakeClient({"reply": f"Yes: sales reached ₪12.5B [{tag}] in FY2024.", "verdict": "spot_on",
                             "credit_own_words": True}))
    r = tutor.review_observation(ctx, "they grow", "l")
    assert r.data["verdict"] == "spot_on" and [t for t, _ in r.sources] == [tag] and r.cost_usd > 0


def test_invented_number_triggers_one_retry_then_fallback(setup):
    _, _, _, ctx = setup
    bad = {"reply": "Sales were ₪99B last year.", "verdict": "partly", "credit_own_words": True}
    good = {"reply": "Sales rose every year.", "verdict": "partly", "credit_own_words": True}
    client = FakeClient(bad, good)
    assert make(client).review_observation(ctx, "x", "l").text == "Sales rose every year."
    correction = client.calls[1]["messages"][-1]["content"]
    assert "₪99B" in correction
    with pytest.raises(Unavailable) as exc:
        make(FakeClient(bad, bad)).review_observation(ctx, "x", "l")
    assert exc.value.reason == "ungrounded"


def test_learner_numbers_may_be_quoted_back(setup):
    _, _, _, ctx = setup
    tutor = make(FakeClient({"reply": "You said ₪20B, but the chart doesn't show that.", "on_topic": True}))
    assert tutor.answer(ctx, "Are sales ₪20B?", [], "l").text.startswith("You said")


def test_buy_sell_advice_is_blocked(setup):
    _, _, _, ctx = setup
    advice = {"reply": "Great company, you should buy the shares.", "on_topic": True}
    with pytest.raises(Unavailable):
        make(FakeClient(advice, advice)).answer(ctx, "Should I buy?", [], "l")


def test_reexplanations_are_cached_and_shared(setup):
    _, _, _, ctx = setup
    client = FakeClient({"reply": "Think of each bar as one year of shopping."})
    store = MemoryStore()
    a = make(client, store).reexplain(ctx, "analogy", "Which year was highest?", ["FY2023", "FY2024"], "FY2023", "l1")
    b = make(client, store).reexplain(ctx, "analogy", "Which year was highest?", ["FY2023", "FY2024"], "FY2023", "l2")
    assert len(client.calls) == 1 and not a.cached and b.cached and b.text == a.text


def test_caps_stop_calls_before_they_cost_anything(setup):
    _, _, _, ctx = setup
    store = MemoryStore()
    for _ in range(CFG["messages_per_learner_per_day"]):
        store.record("heavy", 0.0)
    client = FakeClient()
    with pytest.raises(Unavailable) as exc:
        make(client, store).answer(ctx, "hi", [], "heavy")
    assert exc.value.reason == "learner_cap" and not client.calls
    store.record("someone", CFG["daily_budget_usd"])
    with pytest.raises(Unavailable) as exc:
        make(client, store).answer(ctx, "hi", [], "fresh")
    assert exc.value.reason == "budget" and not client.calls


def test_refusal_and_errors_fall_back(setup):
    _, _, _, ctx = setup
    with pytest.raises(Unavailable) as exc:
        make(FakeClient("refusal")).answer(ctx, "hi", [], "l")
    assert exc.value.reason == "refused"

    class Broken:
        messages = SimpleNamespace(create=lambda **_: (_ for _ in ()).throw(RuntimeError("overloaded")))
    with pytest.raises(Unavailable) as exc:
        make(Broken()).answer(ctx, "hi", [], "l")
    assert exc.value.reason == "error"


def test_pitch_score_is_clamped(setup):
    _, _, _, ctx = setup
    r = make(FakeClient({"reply": "Good.", "growth": True, "cash": True, "peers_or_value": True,
                         "market_belief": True, "score": 9, "recommends_trade": False})).grade_pitch(ctx, "p", "l")
    assert r.data["score"] == 4


def test_cost_formula():
    usage = SimpleNamespace(input_tokens=1_000_000, output_tokens=100_000, cache_read_input_tokens=1_000_000,
                            cache_creation_input_tokens=0)
    assert cost(usage, CFG) == pytest.approx(CFG["price_input_per_mtok"] + CFG["price_output_per_mtok"] / 10
                                             + CFG["price_cache_read_per_mtok"])


def test_learner_profile_lists_new_terms(setup):
    _, _, learner, ctx = setup
    assert "Revenue (sales)" in ctx.learner_profile()
    learner.see(["revenue", "revenue", "fake.same_store_sales", "fake.same_store_sales"])
    learner.concept("revenue").seen = 3
    assert "Revenue (sales)" not in ctx.learner_profile().splitlines()[0]


@pytest.mark.parametrize("reply,ok", [
    ("Revenue was $3.1B [F1], up 19% [F2].", True),
    ("It trades at 3.1x [F3] while peers sit near 8.0x.", False),
    ("Out of every $100 of sales, 3 years later...", True),
    ("Margins of 70-80% are normal here.", True),
    ("Consider selling before it falls.", False),
])
def test_grounding_check(reply, ok):
    from valuation_tutor.core.sector import Fact
    tags = {"F1": Fact("a", "Revenue", 3.13e9, "money", "FY2025", "s"), "F2": Fact("b", "g", 0.1924, "pct", "", "s"),
            "F3": Fact("c", "m", 3.08, "multiple", "", "s")}
    assert grounding.check(reply, tags, ["Gross margins of 70-80% are normal."]).ok is ok


def test_sqlite_store(tmp_path):
    store = SQLiteStore(tmp_path / "t.sqlite")
    store.put("k", {"reply": "hi"})
    assert store.get("k") == {"reply": "hi"} and store.get("missing") is None
    store.record("a", 0.01, date(2026, 10, 1)); store.record("a", 0.02, date(2026, 10, 1))
    store.record("b", 0.05, date(2026, 10, 1))
    assert store.calls_today("a", date(2026, 10, 1)) == 2
    assert store.spend_today(date(2026, 10, 1)) == pytest.approx(0.08)


@pytest.mark.parametrize("text", ["You should buy it.", "Consider selling before it falls.",
                                  "I'd recommend buying now.", "It's a strong buy.", "Time to load up on shares."])
def test_trade_advice_patterns(text):
    assert grounding.check(text, {}, []).recommends_trade


@pytest.mark.parametrize("text", ["Investors buy shares when they expect growth.",
                                  "The price assumes fast growth.", "Selling software by subscription is common."])
def test_explaining_markets_is_not_advice(text):
    assert not grounding.check(text, {}, []).recommends_trade
