"""The learning path: five stages from reading a revenue chart to reverse DCF.

The structure is universal and lives here. A step names the chart *kind* and
concepts it teaches, never a sector's chart id; the sector's charts are matched
to steps by kind and concept. A sector adapts the path with PathChanges
(e.g. SaaS inserts a "pay in shares" step after margins).

Unlocking: levels open one after another within a stage; a stage's boss opens
when all its levels are done; the next stage opens when the boss is beaten.

Level and boss records are kept per sector ("saas:growth"), because finishing
a software lesson isn't finishing the supermarket one. Concept mastery and
badges are not prefixed: those carry across sectors.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace

from . import game
from .learner import Learner
from .sector import ChartDef, SectorModule


@dataclass(frozen=True)
class Step:
    id: str
    concepts: tuple[str, ...]
    chart_kind: str | None = None
    questions: tuple[str, ...] = ()        # generator ids from core.quiz, or "concept:<id>"
    chart_id: str | None = None            # filled in when resolved against a sector
    company: str | None = None             # ticker of the teaching example
    sector: str | None = None              # set for steps a sector added
    capstone: bool = False
    lesson: dict | None = field(default=None, hash=False, compare=False)   # sector steps bring their own text


@dataclass(frozen=True)
class Stage:
    id: str
    rank: str                              # the rank you hold while working through it
    steps: tuple[Step, ...]


CORE_STAGES: list[tuple[str, list[Step]]] = [
    ("story", [
        Step("revenue", ("revenue", "fiscal_year"), "trend", ("trend_peak", "concept:revenue")),
        Step("growth", ("growth",), "trend", ("trend_growth_direction", "concept:growth")),
    ]),
    ("business", [
        Step("margins", ("margin", "gross_margin", "operating_margin"), "margins",
             ("margin_per_hundred", "concept:margin")),
        Step("cash", ("profit", "free_cash_flow"), "profit_vs_cash", ("cash_vs_profit", "concept:free_cash_flow")),
    ]),
    ("peers", [
        Step("multiples", ("multiple", "enterprise_value", "peer_group", "median"), "peers",
             ("peer_position", "concept:multiple")),
    ]),
    ("value", [
        Step("dcf", ("dcf", "share_price"), "price_vs_value", ("value_gap", "concept:dcf")),
        Step("sensitivity", ("sensitivity", "discount_rate", "terminal_value"), "sensitivity",
             ("sensitivity_rate", "concept:discount_rate")),
    ]),
    ("beliefs", [
        Step("implied", ("implied_expectations",), "implied_growth",
             ("implied_vs_actual", "concept:implied_expectations")),
        Step("capstone", ("growth", "free_cash_flow", "multiple", "dcf", "implied_expectations"), None,
             ("trend_growth_direction", "cash_vs_profit", "peer_position", "value_gap", "implied_vs_actual"),
             capstone=True),
    ]),
]


def _match_chart(step: Step, charts: list[ChartDef]) -> ChartDef | None:
    if step.chart_id:
        return next((c for c in charts if c.id == step.chart_id), None)
    of_kind = [c for c in charts if c.kind == step.chart_kind]
    return next((c for c in of_kind if step.concepts[0] in c.concepts), of_kind[0] if of_kind else None)


class LearningPath:
    def __init__(self, sector: SectorModule):
        self.sector = sector
        charts = sector.charts()
        examples = sector.teaching_examples()
        default = examples.get("default") or sector.companies()[0].ticker
        stages = [(sid, list(steps)) for sid, steps in CORE_STAGES]
        self._apply_changes(stages, sector)

        resolved: list[Stage] = []
        for i, (sid, steps) in enumerate(stages):
            kept = []
            for s in steps:
                if s.capstone:
                    kept.append(replace(s, company=examples.get("capstone", default)))
                    continue
                chart = _match_chart(s, charts)
                if chart is None:
                    continue          # this sector has no chart for the step: leave it out
                company = examples.get(s.id) or examples.get(chart.id) or default
                kept.append(replace(s, chart_id=chart.id, chart_kind=chart.kind, company=company))
            if kept:
                resolved.append(Stage(sid, game.RANKS[min(i, len(game.RANKS) - 1)], tuple(kept)))
        self.stages = resolved

    @staticmethod
    def _apply_changes(stages: list[tuple[str, list[Step]]], sector: SectorModule) -> None:
        for change in sector.path_changes():
            for _, steps in stages:
                ids = [s.id for s in steps]
                if change.target not in ids:
                    continue
                i = ids.index(change.target)
                if change.op == "remove":
                    steps.pop(i)
                else:
                    spec = change.step
                    new = Step(id=spec["id"], concepts=tuple(spec["concepts"]), chart_id=spec.get("chart"),
                               chart_kind=spec.get("chart_kind"), questions=tuple(spec.get("questions", ())),
                               sector=sector.id, lesson=spec.get("lesson"))
                    if change.op == "replace":
                        steps[i] = new
                    else:
                        steps.insert(i + 1, new)
                break
            else:
                raise ValueError(f"Path change targets unknown step {change.target!r}")

    # -- lookups ------------------------------------------------------------------

    @property
    def steps(self) -> list[Step]:
        return [s for st in self.stages for s in st.steps]

    def step(self, step_id: str) -> Step:
        return next(s for s in self.steps if s.id == step_id)

    def stage_of(self, step_id: str) -> Stage:
        return next(st for st in self.stages if any(s.id == step_id for s in st.steps))

    def concepts(self) -> list[str]:
        return list(dict.fromkeys(c for s in self.steps for c in s.concepts))

    # -- progress -----------------------------------------------------------------

    def key(self, step_id: str) -> str:
        return f"{self.sector.id}:{step_id}"

    def record(self, learner: Learner, step: Step):
        return learner.step(self.key(step.id))

    def boss_record(self, learner: Learner, stage: Stage):
        return learner.boss(self.key(stage.id))

    def bosses_passed(self, learner: Learner) -> int:
        return sum(self.boss_record(learner, st).passed for st in self.stages)

    def rank(self, learner: Learner) -> str:
        return game.rank_for(self.bosses_passed(learner))

    def stage_unlocked(self, learner: Learner, stage: Stage) -> bool:
        i = self.stages.index(stage)
        return i == 0 or self.boss_record(learner, self.stages[i - 1]).passed

    def step_unlocked(self, learner: Learner, step: Step) -> bool:
        stage = self.stage_of(step.id)
        if not self.stage_unlocked(learner, stage):
            return False
        i = stage.steps.index(step)
        return i == 0 or self.record(learner, stage.steps[i - 1]).completed

    def boss_unlocked(self, learner: Learner, stage: Stage) -> bool:
        return self.stage_unlocked(learner, stage) and all(self.record(learner, s).completed for s in stage.steps)

    def next_up(self, learner: Learner) -> tuple[str, str] | None:
        """("step", id) or ("boss", stage id) for the first thing not yet done, or None when finished."""
        for stage in self.stages:
            for s in stage.steps:
                if not self.record(learner, s).completed:
                    return ("step", s.id)
            if not self.boss_record(learner, stage).passed:
                return ("boss", stage.id)
        return None

    def skippable(self, learner: Learner, step: Step) -> bool:
        """Every concept this step teaches is already mastered (e.g. in another sector)."""
        return not step.capstone and all(learner.mastered(c) for c in step.concepts)
