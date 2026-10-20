"""A tiny invented sector, used to prove the core is sector-agnostic.

Deliberately unlike SaaS: shekels, IFRS, a supermarket-style growth measure
(same-store sales), EBITDA margins instead of gross margins, net income instead
of operating income, no fitted peer line, and one company without a valuation.
Nothing in core/ should need to know any of that.
"""

from valuation_tutor.core.sector import (ChartDef, CompanyData, CompanyRef, Concept, Fact, MetricDef, Note,
                                         PathChange, ProjectionRow, SensitivityGrid, Valuation)

YEARS = ["FY2022", "FY2023", "FY2024"]
COMPANIES = {
    # ticker: (name, sales, same-store growth, ebitda margin, net income, free cash flow)
    "AAA": ("Alef Markets", [10e9, 11e9, 12.5e9], [0.03, 0.05, 0.08], [0.09, 0.10, 0.11], [2e8, 3e8, 4e8],
            [3e8, 2e8, None]),
    "BBB": ("Bet Foods", [8e9, 7.5e9, 7e9], [-0.01, -0.04, -0.02], [0.06, 0.05, 0.03], [1e8, -1e8, -2e8],
            [-5e7, -1e8, -2e8]),
    "CCC": ("Gimel Stores", [4e9, 4.4e9, 4.8e9], [0.02, 0.02, 0.02], [0.08, 0.08, 0.08], [1.5e8, 1.6e8, 1.7e8],
            [1e8, 1.2e8, 1.3e8]),
}
MULTIPLES = {"AAA": 0.9, "BBB": None, "CCC": 0.6}


def _f(ticker, metric, label, unit, period, value, note=""):
    return Fact(f"{ticker}.{metric}.{period}", label, value, unit, period, f"Invented test data for {ticker}",
                note if value is None else "")


class FakeSector:
    id = "fake"
    name = "Fake groceries (test only)"
    currency = "ILS"
    accounting_standard = "IFRS"
    data_as_of = "2026-01-01"

    def __init__(self, locale: str = "en"):
        self.locale = locale

    def companies(self):
        return [CompanyRef(t, n[0], "grocer", "Grocer") for t, n in COMPANIES.items()]

    def metrics(self):
        return [
            MetricDef("sales", "Sales", "money", "Money from shoppers.", concept="revenue"),
            MetricDef("same_store_sales", "Same-store sales growth", "pct",
                      "Growth in stores open at least a year.", concept="fake.same_store_sales"),
            MetricDef("ebitda_margin", "EBITDA margin", "pct", "EBITDA as a share of sales.", concept="margin"),
            MetricDef("net_income", "Net income", "money", "Profit after everything.", concept="profit"),
            MetricDef("fcf", "Free cash flow", "money", "Cash left over.", concept="free_cash_flow"),
            MetricDef("ev_sales", "EV / sales", "multiple", "Enterprise value per shekel of sales.", concept="multiple"),
        ]

    def charts(self):
        return [
            ChartDef("sales", "trend", "Sales", {"bar": "sales", "growth": "same_store_sales"},
                     ("revenue", "fake.same_store_sales"), ("Supermarkets grow slowly.",)),
            ChartDef("sales_plain", "trend", "Sales only", {"bar": "sales"}, ("revenue",)),
            ChartDef("margin", "margins", "Margin", {"first": "ebitda_margin"}, ("margin",),
                     ("IFRS 16 moves rent out of EBITDA, so EBITDA margins look higher.",)),
            ChartDef("cash", "profit_vs_cash", "Cash", {"profit": "net_income", "cash": "fcf"},
                     ("profit", "free_cash_flow")),
            ChartDef("peers", "peers", "Peers", {"value": "ev_sales"}, ("multiple",)),
            ChartDef("fit", "peer_fit", "Fit", {"value": "ev_sales", "x": "same_store_sales"}, ("multiple",)),
            ChartDef("value", "price_vs_value", "Value", {}, ("dcf",)),
            ChartDef("implied", "implied_growth", "Implied", {}, ("implied_expectations",)),
            ChartDef("sens", "sensitivity", "Sensitivity", {}, ("sensitivity",)),
        ]

    def concepts(self):
        return [Concept("fake.same_store_sales", "Same-store sales", "Growth from existing stores only.",
                        prerequisites=("growth",), sector=self.id)]

    def path_changes(self):
        return [PathChange("insert_after", "growth", {
            "id": "same_store_sales", "concepts": ["fake.same_store_sales"], "chart": "sales",
            "questions": ["trend_growth_direction"],
            "lesson": {"title": "Same-store sales", "intro": "Growth from existing stores.",
                       "look_prompt": "What do you see?", "takeaway": "New stores flatter growth."}})]

    def teaching_examples(self):
        return {"default": "AAA"}

    def headline_metrics(self):
        return ["sales", "same_store_sales", "ev_sales"]

    def accounting_notes(self):
        return [Note("ifrs16", "IFRS 16", "Store leases are on the balance sheet.")]

    def company_data(self, ticker: str) -> CompanyData:
        name, sales, sss, margin, ni, fcf = COMPANIES[ticker]
        ref = CompanyRef(ticker, name, "grocer", "Grocer")
        history = {
            "sales": [_f(ticker, "sales", "Sales", "money", p, v) for p, v in zip(YEARS, sales)],
            "same_store_sales": [_f(ticker, "same_store_sales", "Same-store sales growth", "pct", p, v)
                                 for p, v in zip(YEARS, sss)],
            "ebitda_margin": [_f(ticker, "ebitda_margin", "EBITDA margin", "pct", p, v) for p, v in zip(YEARS, margin)],
            "net_income": [_f(ticker, "net_income", "Net income", "money", p, v) for p, v in zip(YEARS, ni)],
            "fcf": [_f(ticker, "fcf", "Free cash flow", "money", p, v, "Not reported") for p, v in zip(YEARS, fcf)],
        }
        peers = [(CompanyRef(t, n[0], "grocer", "Grocer"),
                  {"ev_sales": _f(t, "ev_sales", "EV / sales", "multiple", "2024", MULTIPLES[t], "Negative EBITDA"),
                   "same_store_sales": _f(t, "same_store_sales", "Same-store sales growth", "pct", "2024", n[2][-1])})
                 for t, n in COMPANIES.items()]
        return CompanyData(ref=ref, history=history, snapshot=dict(peers[list(COMPANIES).index(ticker)][1]),
                           peers=peers, valuation=self._valuation(ticker) if ticker == "AAA" else None)

    def _valuation(self, ticker):
        def v(metric, value, unit="pct"):
            return _f(ticker, metric, metric, unit, "2026", value)
        return Valuation(
            price=v("price", 50.0, "per_share"), fair_value=v("dcf_value", 60.0, "per_share"),
            implied_growth=v("implied", 0.06), actual_growth=v("actual", 0.08), discount_rate=v("rate", 0.09),
            terminal_growth=v("tg", 0.02), terminal_share=v("tv_share", 0.55),
            projection=[ProjectionRow("2025", "explicit", v("rev25", 13e9, "money"), v("fcf25", 4e8, "money"))],
            sensitivity=SensitivityGrid("Discount rate", "Long-term growth", [0.08, 0.09, 0.10], [0.015, 0.02, 0.025],
                                        [[70, 75, 81], [56, 60, 64], [46, 49, None]], 0.09, 0.02, "Invented"),
            method_note="Invented.")
