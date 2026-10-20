"""Check every number in a tutor reply against what the tutor was given.

The tutor may only repeat numbers from the fact sheet, the observations, the
lesson and notes, or the learner's own message. This module pulls every
number out of a reply and looks for it in those sources, at the precision the
reply shows it ("$3.1B" matches 3,130,000,000; "19%" matches 0.1924). Fact
tags like [F3] must name a fact that exists. A trading recommendation is
caught here too, as a second line of defence behind the prompt.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from ..sector import Fact

NUMBER = re.compile(
    r"(?P<neg>[-−])?(?P<cur>[$₪€£])?(?P<num>\d{1,3}(?:,\d{3})+|\d+)(?P<dec>\.\d+)?"
    r"\s?(?P<unit>%|x\b|times\b|B\b|M\b|K\b|bn\b|billion\b|million\b|percentage points?\b)?",
    re.IGNORECASE)
TAG = re.compile(r"\[(F\d+)\]")
YEAR = re.compile(r"^(19|20)\d\d$")
SCALE = {"b": 1e9, "bn": 1e9, "billion": 1e9, "m": 1e6, "million": 1e6, "k": 1e3}
TRADE = re.compile(
    r"\b(you should|i'?d|i would|i recommend|we recommend|consider|go ahead and|time to)\b[^.]{0,40}"
    r"\b(buy(ing)?|sell(ing)?|short(ing)?|invest(ing)? in|load(ing)? up)\b"
    r"|\b(strong buy|a buy|a sell|undervalued gem|must[- ]own)\b",
    re.IGNORECASE)


@dataclass(frozen=True)
class Num:
    shown: float          # as written: 3.1 in "$3.1B", 19 in "19%"
    scale: float          # multiply to get base units: 1e9 for "B", 0.01 for "%"
    decimals: int         # decimals as written
    kind: str             # "pct", "multiple", "money", "plain"
    text: str

    @property
    def value(self) -> float:
        return self.shown * self.scale

    def matches(self, candidate: float) -> bool:
        """Does `candidate` (base units) round to what was written?"""
        return abs(candidate / self.scale - self.shown) <= 0.5 * 10 ** -self.decimals + 1e-9


def parse(text: str) -> list[Num]:
    out = []
    for m in NUMBER.finditer(text):
        dec = m.group("dec") or ""
        shown = float(m.group("num").replace(",", "") + dec) * (-1 if m.group("neg") else 1)
        decimals = max(len(dec) - 1, 0)
        unit = (m.group("unit") or "").lower()
        if unit == "%" or unit.startswith("percentage"):
            kind, scale = "pct", 0.01
        elif unit in ("x", "times"):
            kind, scale = "multiple", 1.0
        elif unit in SCALE or m.group("cur"):
            kind, scale = "money", SCALE.get(unit, 1.0)
        else:
            kind, scale = "plain", 1.0
        out.append(Num(shown, scale, decimals, kind, m.group(0)))
    return out


@dataclass
class Grounding:
    ok: bool
    unverified: list[str] = field(default_factory=list)
    bad_tags: list[str] = field(default_factory=list)
    recommends_trade: bool = False


def allowed_values(facts: list[Fact], texts: list[str]) -> list[tuple[str, float]]:
    """(kind, value in base units) for everything the tutor may repeat."""
    kinds = {"pct": "pct", "multiple": "multiple", "money": "money", "per_share": "money"}
    out = [(kinds.get(f.unit, "plain"), f.value) for f in facts if f.value is not None]
    return out + [(n.kind, n.value) for t in texts for n in parse(t)]


def check(reply: str, tags: dict[str, Fact], texts: list[str]) -> Grounding:
    allowed = allowed_values(list(tags.values()), texts)
    unverified = []
    for n in parse(TAG.sub("", reply)):
        if n.kind == "plain" and (YEAR.match(n.text.strip()) or (n.shown.is_integer() and 0 <= n.shown <= 12)):
            continue                     # years and small counts ("3 years")
        if n.kind in ("plain", "money") and n.scale == 1 and n.shown in (1, 100):
            continue                     # teaching phrases: "for every $1", "out of every $100"
        ok_kinds = {n.kind, "multiple"} if n.kind == "plain" else {n.kind}
        if not any(kind in ok_kinds and n.matches(v) for kind, v in allowed):
            unverified.append(n.text.strip())
    bad_tags = [t for t in TAG.findall(reply) if t not in tags]
    trade = bool(TRADE.search(reply))
    return Grounding(not unverified and not bad_tags and not trade, unverified, bad_tags, trade)
