"""Number formatting for learners: "$3.1B", "19%", "4.0x", "$230.94".

Kept in one place so every chart label, explanation and tutor answer shows a
number the same way, and so the grounding check can match what the tutor
writes against the Facts it was given.
"""

from __future__ import annotations

import math

from .i18n import Translator
from .sector import Fact, Unit

CURRENCY_SYMBOLS = {"USD": "$", "ILS": "₪", "EUR": "€", "GBP": "£"}


def is_missing(value) -> bool:
    return value is None or (isinstance(value, float) and math.isnan(value))


class Formatter:
    def __init__(self, currency: str, t: Translator):
        self.currency = currency
        self.symbol = CURRENCY_SYMBOLS.get(currency, currency + " ")
        self.t = t

    def money(self, value: float | None) -> str:
        if is_missing(value):
            return self.t.t("fmt.missing")
        sign = "-" if value < 0 else ""
        v = abs(value)
        if v >= 1e9:
            return f"{sign}{self.symbol}{v / 1e9:,.1f}{self.t.t('fmt.billion')}"
        if v >= 1e6:
            return f"{sign}{self.symbol}{v / 1e6:,.0f}{self.t.t('fmt.million')}"
        return f"{sign}{self.symbol}{v:,.0f}"

    def pct(self, value: float | None, signed: bool = False, decimals: int | None = None) -> str:
        """19% / 4.3% by default; pass decimals for rates where 10.7% vs 11% matters."""
        if is_missing(value):
            return self.t.t("fmt.missing")
        p = value * 100
        digits = decimals if decimals is not None else (1 if abs(p) < 10 and round(p, 1) != round(p) else 0)
        return f"{p:+.{digits}f}%" if signed else f"{p:.{digits}f}%"

    def multiple(self, value: float | None) -> str:
        return self.t.t("fmt.missing") if is_missing(value) else f"{value:.1f}x"

    def per_share(self, value: float | None) -> str:
        return self.t.t("fmt.missing") if is_missing(value) else f"{self.symbol}{value:,.2f}"

    def number(self, value: float | None) -> str:
        return self.t.t("fmt.missing") if is_missing(value) else f"{value:,.0f}"

    def value(self, value: float | None, unit: Unit) -> str:
        return {"money": self.money, "pct": self.pct, "multiple": self.multiple,
                "per_share": self.per_share, "number": self.number}[unit](value)

    def fact(self, fact: Fact) -> str:
        return self.value(fact.value, fact.unit)

    def money_scale(self, values: list[float]) -> tuple[float, str]:
        """Divisor and axis title for a money axis, e.g. (1e9, "$ billions")."""
        top = max((abs(v) for v in values if not is_missing(v)), default=0)
        if top >= 1e9:
            return 1e9, self.t.t("fmt.axis_billions", symbol=self.symbol)
        return 1e6, self.t.t("fmt.axis_millions", symbol=self.symbol)
