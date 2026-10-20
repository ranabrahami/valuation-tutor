"""Check-for-understanding questions, generated from the real data.

Each generator reads one chart's Facts and asks something the chart answers
("In which year was revenue highest?"), so the right answer is computed, not
written by hand, and the same question works for any company in any sector.
Concept questions ("concept:<id>") are fixed multiple choice from the locale
(or from a sector Concept's `check`).

Bosses use a mystery company: its name is hidden so the learner has to read
the charts rather than recall what they know about the brand.
"""

from __future__ import annotations

import random
from dataclasses import dataclass, replace

from . import game
from .charts import KINDS, ChartContext
from .charts.history import STEADY, present
from .charts.peers import company_fact, peer_values
from .explain import Explainer
from .sector import CompanyData, Concept


@dataclass(frozen=True)
class Question:
    id: str                       # generator id
    variant: str                  # generator + company: two different variants count toward mastery
    prompt: str
    options: tuple[str, ...]
    answer: int                   # index into options
    why: str                      # shown after answering
    concepts: tuple[str, ...]
    facts: tuple[str, ...] = ()
    chart_id: str | None = None
    ticker: str | None = None


def _q(gen, ctx: ChartContext, prompt, options, answer, why, concepts, facts=()) -> Question:
    return Question(gen, f"{gen}:{ctx.data.ref.ticker}", prompt, tuple(options), answer, why, tuple(concepts),
                    tuple(facts), ctx.chart.id, ctx.data.ref.ticker)


# ---------------------------------------------------------------------------
# Generators: (ChartContext) -> Question | None
# ---------------------------------------------------------------------------

def trend_peak(ctx: ChartContext):
    have = present(ctx.series("bar"))[-4:]
    if len(have) < 2:
        return None
    best = max(have, key=lambda f: f.value)
    t = ctx.t
    return _q("trend_peak", ctx, t.t("quiz.trend_peak.prompt", label=ctx.label("bar").lower(), company=ctx.company),
              [f.period for f in have], have.index(best),
              t.t("quiz.trend_peak.why", period=best.period, value=ctx.fmt.fact(best)),
              ("revenue",), [f.id for f in have])


def trend_growth_direction(ctx: ChartContext):
    growth = present(ctx.series("growth"))
    if len(growth) < 2:
        return None
    g0, g1 = growth[0], growth[-1]
    answer = 1 if g1.value < g0.value - STEADY else 0 if g1.value > g0.value + STEADY else 2
    t = ctx.t
    return _q("trend_growth_direction", ctx,
              t.t("quiz.growth_direction.prompt", company=ctx.company, first_period=g0.period, last_period=g1.period),
              [t.t("quiz.options.faster"), t.t("quiz.options.slower"), t.t("quiz.options.about_same")], answer,
              t.t("quiz.growth_direction.why", first=ctx.fmt.fact(g0), first_period=g0.period,
                  last=ctx.fmt.fact(g1), last_period=g1.period),
              ("growth",), (g0.id, g1.id))


def margin_per_hundred(ctx: ChartContext):
    have = present(ctx.series("first"))
    if not have:
        return None
    last = have[-1]
    keep = round(last.value * 100)
    if not 5 <= keep <= 95:
        return None
    # Wrong options that test real confusions: the costs instead of what's kept,
    # and (if shown) the other margin on the chart.
    other = present(ctx.series("second"))
    third = round(other[-1].value * 100) if other else keep // 2
    options = sorted({keep, 100 - keep, third})
    if len(options) < 3 or min(abs(a - b) for a in options for b in options if a != b) < 4:
        options = sorted({keep, 100 - keep, keep // 2})
    if len(options) < 3:
        return None
    sym, t = ctx.fmt.symbol, ctx.t
    return _q("margin_per_hundred", ctx,
              t.t("quiz.margin_per_hundred.prompt", symbol=sym, period=last.period, company=ctx.company,
                  label=last.label.lower()),
              [f"{sym}{o}" for o in options], options.index(keep),
              t.t("quiz.margin_per_hundred.why", label=last.label, value=ctx.fmt.fact(last), symbol=sym, keep=keep),
              ("margin",), (last.id,))


def trend_any_fall(ctx: ChartContext):
    have = present(ctx.series("bar"))
    if len(have) < 3:
        return None
    falls = [b for a, b in zip(have, have[1:]) if b.value < a.value]
    t = ctx.t
    why = (t.t("quiz.trend_any_fall.why_yes", periods=", ".join(f.period for f in falls)) if falls
           else t.t("quiz.trend_any_fall.why_no", first=have[0].period, last=have[-1].period))
    return _q("trend_any_fall", ctx, t.t("quiz.trend_any_fall.prompt", company=ctx.company,
                                         label=ctx.label("bar").lower()),
              [t.t("quiz.options.yes"), t.t("quiz.options.no")], 0 if falls else 1, why,
              ("revenue",), [f.id for f in have])


def margin_direction(ctx: ChartContext):
    have = present(ctx.series("first"))
    if len(have) < 2:
        return None
    a, b = have[0], have[-1]
    answer = 0 if b.value > a.value + STEADY else 1 if b.value < a.value - STEADY else 2
    t = ctx.t
    return _q("margin_direction", ctx,
              t.t("quiz.margin_direction.prompt", label=a.label.lower(), first_period=a.period, last_period=b.period,
                  company=ctx.company),
              [t.t("quiz.options.up"), t.t("quiz.options.down"), t.t("quiz.options.about_same")], answer,
              t.t("quiz.margin_direction.why", label=a.label, first=ctx.fmt.fact(a), last=ctx.fmt.fact(b),
                  first_period=a.period, last_period=b.period),
              (ctx.metric("first").concept or "margin",), (a.id, b.id))


def cash_vs_profit(ctx: ChartContext):
    profit = {f.period: f for f in present(ctx.series("profit"))}
    cash = {f.period: f for f in present(ctx.series("cash"))}
    common = [p for p in profit if p in cash]
    if not common:
        return None
    p, c = profit[common[-1]], cash[common[-1]]
    t = ctx.t
    return _q("cash_vs_profit", ctx,
              t.t("quiz.cash_vs_profit.prompt", company=ctx.company, period=p.period),
              [p.label, c.label], 0 if p.value > c.value else 1,
              t.t("quiz.cash_vs_profit.why", profit_label=p.label, profit=ctx.fmt.fact(p), cash_label=c.label,
                  cash=ctx.fmt.fact(c)),
              ("profit", "free_cash_flow"), (p.id, c.id))


def peer_position(ctx: ChartContext):
    metric = ctx.chart.roles["value"]
    rows, mine = peer_values(ctx, metric), company_fact(ctx, metric)
    if mine is None or mine.missing or len(rows) < 3:
        return None
    values = sorted(f.value for _, _, f in rows)
    median = values[len(values) // 2] if len(values) % 2 else (values[len(values) // 2 - 1] + values[len(values) // 2]) / 2
    t = ctx.t
    return _q("peer_position", ctx,
              t.t("quiz.peer_position.prompt", company=ctx.company, label=ctx.label("value")),
              [t.t("quiz.options.above_median"), t.t("quiz.options.below_median")], 0 if mine.value > median else 1,
              t.t("quiz.peer_position.why", company=ctx.company, value=ctx.fmt.fact(mine),
                  median=ctx.fmt.value(median, mine.unit)),
              ("multiple", "peer_group", "median"), (mine.id,))


def peer_vs_peer(ctx: ChartContext):
    """Which of two named companies is more expensive? Uses the peer closest to the median."""
    metric = ctx.chart.roles["value"]
    rows, mine = peer_values(ctx, metric), company_fact(ctx, metric)
    if mine is None or mine.missing or len(rows) < 3:
        return None
    others = [(name, f) for tk, name, f in rows if tk != ctx.data.ref.ticker and abs(f.value / mine.value - 1) > 0.2]
    if not others:
        return None
    values = sorted(f.value for _, f in others)
    name, other = min(others, key=lambda r: abs(r[1].value - values[len(values) // 2]))
    t = ctx.t
    return _q("peer_vs_peer", ctx, t.t("quiz.peer_vs_peer.prompt", company=ctx.company, other=name,
                                       label=ctx.label("value")),
              [ctx.company, name], 0 if mine.value > other.value else 1,
              t.t("quiz.peer_vs_peer.why", company=ctx.company, value=ctx.fmt.fact(mine), other=name,
                  other_value=ctx.fmt.fact(other)),
              ("multiple", "peer_group"), (mine.id, other.id))


def fit_side(ctx: ChartContext):
    kind = KINDS["peer_fit"]
    derived = kind.derived_facts(ctx)
    mine = company_fact(ctx, ctx.chart.roles["value"])
    if not derived or mine is None or mine.missing:
        return None
    line = derived[0]
    t = ctx.t
    return _q("fit_side", ctx, t.t("quiz.fit_side.prompt", company=ctx.company, x=ctx.label("x").lower()),
              [t.t("quiz.options.above_line"), t.t("quiz.options.below_line")], 0 if mine.value > line.value else 1,
              t.t("quiz.fit_side.why", company=ctx.company, actual=ctx.fmt.fact(mine), line=ctx.fmt.fact(line),
                  x=ctx.label("x").lower()),
              ("multiple", "growth"), (mine.id, line.id))


def value_gap(ctx: ChartContext):
    v = ctx.data.valuation
    if v is None or v.fair_value.missing:
        return None
    t = ctx.t
    return _q("value_gap", ctx, t.t("quiz.value_gap.prompt", company=ctx.company),
              [t.t("quiz.options.model_higher"), t.t("quiz.options.model_lower")],
              0 if v.fair_value.value > v.price.value else 1,
              t.t("quiz.value_gap.why", value=ctx.fmt.fact(v.fair_value), price=ctx.fmt.fact(v.price)),
              ("dcf", "share_price"), (v.fair_value.id, v.price.id))


def terminal_share(ctx: ChartContext):
    v = ctx.data.valuation
    if v is None or v.terminal_share.missing:
        return None
    t = ctx.t
    return _q("terminal_share", ctx, t.t("quiz.terminal_share.prompt", company=ctx.company),
              [t.t("quiz.options.more_than_half"), t.t("quiz.options.less_than_half")],
              0 if v.terminal_share.value > 0.5 else 1,
              t.t("quiz.terminal_share.why", share=ctx.fmt.fact(v.terminal_share)),
              ("terminal_value", "dcf"), (v.terminal_share.id,))


def sensitivity_majority(ctx: ChartContext):
    v = ctx.data.valuation
    if v is None:
        return None
    cells = [x for row in v.sensitivity.values for x in row if x is not None]
    if not cells:
        return None
    above = sum(x > v.price.value for x in cells)
    share = above / len(cells)
    t = ctx.t
    return _q("sensitivity_majority", ctx, t.t("quiz.sensitivity_majority.prompt", price=ctx.fmt.fact(v.price)),
              [t.t("quiz.options.most_boxes"), t.t("quiz.options.about_half"), t.t("quiz.options.few_boxes")],
              0 if share >= 0.7 else 2 if share <= 0.3 else 1,
              t.t("quiz.sensitivity_majority.why", above=above, total=len(cells)),
              ("sensitivity",), (v.price.id,))


def sensitivity_closest(ctx: ChartContext):
    """Stress test: which assumptions make the model agree with today's price?"""
    v = ctx.data.valuation
    if v is None:
        return None
    s, price = v.sensitivity, v.price.value
    cells = [(abs(s.values[i][j] / price - 1), i, j) for i in range(len(s.rates)) for j in range(len(s.growths))
             if s.values[i][j] is not None]
    if len(cells) < 3:
        return None
    cells.sort()
    best, far = cells[0], cells[-1]
    mid = cells[len(cells) // 2]
    if len({(c[1], c[2]) for c in (best, mid, far)}) < 3 or mid[0] - best[0] < 0.05:
        return None
    fmt, t = ctx.fmt, ctx.t

    def label(c):
        return t.t("quiz.sensitivity_closest.option", rate=fmt.pct(s.rates[c[1]], decimals=1),
                   growth=fmt.pct(s.growths[c[2]], decimals=1))

    options = [label(best), label(mid), label(far)]
    return _q("sensitivity_closest", ctx, t.t("quiz.sensitivity_closest.prompt", price=fmt.fact(v.price)),
              options, 0,
              t.t("quiz.sensitivity_closest.why", value=fmt.per_share(s.values[best[1]][best[2]]),
                  price=fmt.fact(v.price)),
              ("sensitivity", "implied_expectations"), (v.price.id,))


def sensitivity_rate(ctx: ChartContext):
    v = ctx.data.valuation
    if v is None:
        return None
    s = v.sensitivity
    bi = min(range(len(s.rates)), key=lambda i: abs(s.rates[i] - s.base_rate))
    bj = min(range(len(s.growths)), key=lambda j: abs(s.growths[j] - s.base_growth))
    if bi + 1 >= len(s.rates) or s.values[bi][bj] is None or s.values[bi + 1][bj] is None:
        return None
    base, higher = s.values[bi][bj], s.values[bi + 1][bj]
    t, fmt = ctx.t, ctx.fmt
    return _q("sensitivity_rate", ctx, t.t("quiz.sensitivity_rate.prompt"),
              [t.t("quiz.options.goes_up"), t.t("quiz.options.goes_down"), t.t("quiz.options.stays_same")],
              0 if higher > base else 1 if higher < base else 2,
              t.t("quiz.sensitivity_rate.why", base=fmt.per_share(base), higher=fmt.per_share(higher),
                  rate=fmt.pct(s.rates[bi + 1], decimals=1)),
              ("discount_rate", "sensitivity"))


def implied_vs_actual(ctx: ChartContext):
    v = ctx.data.valuation
    if v is None or v.implied_growth.missing or v.actual_growth.missing:
        return None
    t = ctx.t
    return _q("implied_vs_actual", ctx, t.t("quiz.implied_vs_actual.prompt", company=ctx.company),
              [t.t("quiz.options.faster"), t.t("quiz.options.slower")],
              0 if v.implied_growth.value > v.actual_growth.value else 1,
              t.t("quiz.implied_vs_actual.why", implied=ctx.fmt.fact(v.implied_growth),
                  actual=ctx.fmt.fact(v.actual_growth)),
              ("implied_expectations",), (v.implied_growth.id, v.actual_growth.id))


GENERATORS = {f.__name__: f for f in (trend_peak, trend_growth_direction, trend_any_fall, margin_per_hundred,
                                       margin_direction,
                                       cash_vs_profit, peer_position, peer_vs_peer, fit_side, value_gap,
                                       terminal_share, sensitivity_rate, sensitivity_majority,
                                       sensitivity_closest,
                                       implied_vs_actual)}
# Which generators can run on each chart kind (used by bosses and sector steps).
BY_KIND = {
    "trend": ("trend_peak", "trend_growth_direction", "trend_any_fall"),
    "margins": ("margin_per_hundred", "margin_direction"),
    "profit_vs_cash": ("cash_vs_profit",),
    "peers": ("peer_position", "peer_vs_peer"),
    "peer_fit": ("fit_side",),
    "price_vs_value": ("value_gap", "terminal_share"),
    "sensitivity": ("sensitivity_rate", "sensitivity_majority", "sensitivity_closest"),
    "implied_growth": ("implied_vs_actual",),
}


# ---------------------------------------------------------------------------
# Building question sets
# ---------------------------------------------------------------------------

def concept_question(concept: Concept, t) -> Question | None:
    """Fixed multiple choice about an idea, from the locale or the sector's Concept.check."""
    spec = concept.check or (t.get(f"quiz.concepts.{concept.id}") if concept.sector is None else None)
    if not spec:
        return None
    return Question(f"concept:{concept.id}", f"concept:{concept.id}", spec["prompt"], tuple(spec["options"]),
                    int(spec["answer"]), spec["why"], (concept.id,))


def shuffled(q: Question, seed: str) -> Question:
    """Shuffle options (stable per seed) so the right answer isn't always in the same place."""
    order = list(range(len(q.options)))
    if q.id in ("trend_peak",):            # years keep their natural order
        return q
    random.Random(seed).shuffle(order)
    return replace(q, options=tuple(q.options[i] for i in order), answer=order.index(q.answer))


class QuizMaker:
    def __init__(self, explainer: Explainer):
        self.ex = explainer
        self.sector = explainer.sector

    def generate(self, gen_id: str, data: CompanyData, chart_id: str) -> Question | None:
        chart = self.ex.charts.get(chart_id)
        if chart is None:
            return None
        return GENERATORS[gen_id](self.ex.context(data, chart))

    def for_step(self, step, data_for, seed: str = "") -> list[Question]:
        """Questions for a level. data_for(ticker) returns CompanyData."""
        out = []
        questions = step.questions or tuple(f"concept:{c}" for c in step.concepts[:1])
        if step.chart_id and not any(q in GENERATORS for q in questions):
            questions = BY_KIND.get(step.chart_kind, ())[:1] + questions
        for gen in questions:
            if gen.startswith("concept:"):
                cid = gen.split(":", 1)[1]
                q = concept_question(self.ex.concepts[cid], self.ex.t) if cid in self.ex.concepts else None
            elif step.capstone:
                kind = next(k for k, gens in BY_KIND.items() if gen in gens)
                chart = next((c for c in self.ex.charts.values() if c.kind == kind), None)
                q = self.generate(gen, data_for(step.company), chart.id) if chart else None
            else:
                q = self.generate(gen, data_for(step.company), step.chart_id)
            if q:
                out.append(shuffled(q, f"{seed}{q.variant}"))
        return out

    def boss(self, stage, data_for, attempt: int, exclude: set[str]) -> tuple[str, list[Question]]:
        """A mystery company and BOSS_QUESTIONS questions across the stage's charts."""
        rng = random.Random(f"{stage.id}:{attempt}")
        candidates = [c.ticker for c in self.sector.companies() if c.ticker not in exclude]
        rng.shuffle(candidates)
        plan = list(dict.fromkeys((s.chart_id, gen) for s in stage.steps if s.chart_id
                                  for gen in BY_KIND.get(s.chart_kind, ())))
        if not plan or any(s.capstone for s in stage.steps):   # the final boss draws on every chart
            plan = [(c.id, gen) for c in self.ex.charts.values() for gen in BY_KIND.get(c.kind, ())]
            rng.shuffle(plan)
        for ticker in candidates:
            data = mask(data_for(ticker), self.ex.t.t("game.mystery_name"))
            questions = [q for chart_id, gen in plan if (q := self.generate(gen, data, chart_id))]
            picked = _spread(questions, game.BOSS_QUESTIONS)
            if len(picked) == game.BOSS_QUESTIONS:
                return ticker, [shuffled(q, f"{attempt}{q.variant}") for q in picked]
        raise ValueError(f"No company can supply a boss for stage {stage.id}")


def _spread(questions: list[Question], n: int) -> list[Question]:
    """Pick n questions, preferring different charts and different question types."""
    picked: list[Question] = []
    for rule in (lambda q: q.chart_id not in {p.chart_id for p in picked} and q.id not in {p.id for p in picked},
                 lambda q: q.id not in {p.id for p in picked},
                 lambda q: True):
        for q in questions:
            if len(picked) < n and q not in picked and rule(q):
                picked.append(q)
    return picked


def mask(data: CompanyData, name: str) -> CompanyData:
    """Hide the company's name in its own data (for mystery bosses). Ids stay the same."""
    ref = replace(data.ref, name=name)
    peers = [(ref if r.ticker == data.ref.ticker else r, v) for r, v in data.peers]
    return replace(data, ref=ref, peers=peers)
