"""The learner model: what someone has seen, got right, and struggled with.

Plain data plus rules, so it's testable and can be saved anywhere (session
state now, a database from milestone 4). Pacing is decided here, by code:
  * a concept is mastered after two correct answers in a row, on two different
    questions or companies (one lucky guess isn't understanding);
  * after a mistake, the next explanation uses a style not yet tried
    (plain words -> everyday analogy -> another company -> the idea it builds on);
  * concepts already mastered can be skipped, which is how a fast learner
    (or one coming back from another sector) moves quickly.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import date, timedelta

from . import game

STYLES = ["plain", "analogy", "other_company", "prerequisite"]


@dataclass
class ConceptState:
    seen: int = 0
    attempts: int = 0
    correct: int = 0
    streak: int = 0                  # correct answers in a row
    struggles: int = 0               # wrong answers and "I don't get it"
    recent_variants: list[str] = field(default_factory=list)   # variants of the current streak
    styles_tried: list[str] = field(default_factory=list)
    mastered: bool = False


@dataclass
class StepRecord:
    completed: bool = False
    stars: int = 0
    observation: str = ""            # what the learner wrote before seeing the explanation
    own_words: bool | None = None    # the tutor's verdict on it; None = no tutor, use the word count


@dataclass
class BossRecord:
    attempts: int = 0
    passed: bool = False
    best: int = 0


@dataclass
class AnswerOutcome:
    correct: bool
    xp: int
    newly_mastered: list[str]
    new_badges: list[str]
    next_style: str | None            # how to re-explain after a mistake


@dataclass
class Learner:
    concepts: dict[str, ConceptState] = field(default_factory=dict)
    steps: dict[str, StepRecord] = field(default_factory=dict)
    bosses: dict[str, BossRecord] = field(default_factory=dict)
    xp: int = 0
    hints: int = game.STARTING_HINTS
    badges: list[str] = field(default_factory=list)
    streak_days: int = 0
    last_active: str | None = None
    freeze_available: bool = True

    # -- concepts ---------------------------------------------------------------

    def concept(self, cid: str) -> ConceptState:
        return self.concepts.setdefault(cid, ConceptState())

    def see(self, concept_ids) -> None:
        for cid in concept_ids:
            self.concept(cid).seen += 1

    def is_new(self, cid: str) -> bool:
        """True the first time a term appears: the UI then explains it in plain words."""
        return self.concept(cid).seen == 0

    def mastered(self, cid: str) -> bool:
        return self.concepts.get(cid, ConceptState()).mastered

    def answer(self, concept_ids, correct: bool, variant: str, first_try: bool) -> AnswerOutcome:
        """Record one answer to a check question about these concepts."""
        newly = []
        for cid in concept_ids:
            c = self.concept(cid)
            c.attempts += 1
            if correct:
                c.correct += 1
                c.streak += 1
                c.recent_variants = (c.recent_variants + [variant])[-2:]
                if not c.mastered and c.streak >= 2 and len(set(c.recent_variants)) == 2:
                    c.mastered = True
                    newly.append(cid)
            else:
                c.streak, c.recent_variants = 0, []
                c.struggles += 1
        xp = (game.XP_CORRECT_FIRST_TRY if first_try else game.XP_CORRECT_AFTER_RETRY) if correct else 0
        self.xp += xp
        return AnswerOutcome(correct, xp, newly, self._award_badges(),
                             None if correct else self.next_style(concept_ids))

    def struggle(self, concept_ids) -> str:
        """The learner said "I don't get it": counts as a struggle, returns the next style to try."""
        for cid in concept_ids:
            self.concept(cid).struggles += 1
        return self.next_style(concept_ids)

    def next_style(self, concept_ids) -> str:
        tried = set().union(*(self.concept(c).styles_tried for c in concept_ids)) if concept_ids else set()
        style = next((s for s in STYLES if s not in tried), STYLES[-1])
        for cid in concept_ids:
            if style not in self.concept(cid).styles_tried:
                self.concept(cid).styles_tried.append(style)
        return style

    def _award_badges(self) -> list[str]:
        new = [b for b, needed in game.BADGES.items()
               if b not in self.badges and all(self.mastered(c) for c in needed)]
        self.badges += new
        return new

    # -- steps and bosses -------------------------------------------------------

    def step(self, step_id: str) -> StepRecord:
        return self.steps.setdefault(step_id, StepRecord())

    def write_observation(self, step_id: str, text: str) -> int:
        """Store what the learner noticed; a real attempt earns a little XP once."""
        rec = self.step(step_id)
        first = game.counts_as_own_words(text) and not game.counts_as_own_words(rec.observation)
        rec.observation = text.strip()
        if first:
            self.xp += game.XP_OBSERVATION
            return game.XP_OBSERVATION
        return 0

    def judge_observation(self, step_id: str, credit: bool) -> None:
        """The tutor read the observation and decided whether it earns the "own words" star."""
        self.step(step_id).own_words = credit

    def award(self, xp: int) -> None:
        self.xp += max(0, xp)

    def complete_step(self, step_id: str, right_first_time: bool, today: date | None = None) -> int:
        rec = self.step(step_id)
        own = rec.own_words if rec.own_words is not None else game.counts_as_own_words(rec.observation)
        stars = game.stars_for(True, right_first_time, own)
        rec.completed, rec.stars = True, max(rec.stars, stars)
        self.touch(today)
        return stars

    def skip_step(self, step_id: str, today: date | None = None) -> None:
        """Skip a level whose concepts are already mastered: counts as done, 2 stars."""
        rec = self.step(step_id)
        rec.completed, rec.stars = True, max(rec.stars, 2)
        self.touch(today)

    def boss(self, stage_id: str) -> BossRecord:
        return self.bosses.setdefault(stage_id, BossRecord())

    def finish_boss(self, stage_id: str, score: int, today: date | None = None) -> bool:
        rec = self.boss(stage_id)
        rec.attempts += 1
        rec.best = max(rec.best, score)
        passed_now = score >= game.BOSS_PASS_MARK and not rec.passed
        if passed_now:
            rec.passed = True
            self.xp += game.XP_BOSS_PASSED
            self.hints += game.HINTS_PER_BOSS
        self.touch(today)
        return score >= game.BOSS_PASS_MARK

    @property
    def bosses_passed(self) -> int:
        return sum(b.passed for b in self.bosses.values())

    @property
    def rank(self) -> str:
        return game.rank_for(self.bosses_passed)

    def use_hint(self) -> bool:
        if self.hints <= 0:
            return False
        self.hints -= 1
        return True

    # -- streak -------------------------------------------------------------------

    def touch(self, today: date | None = None) -> None:
        """Count today as an active day. One missed day is forgiven by a free freeze."""
        today = today or date.today()
        last = date.fromisoformat(self.last_active) if self.last_active else None
        if last == today:
            return
        if last == today - timedelta(days=1):
            self.streak_days += 1
        elif last == today - timedelta(days=2) and self.freeze_available:
            self.freeze_available = False
            self.streak_days += 1
        else:
            self.streak_days = 1
        self.last_active = today.isoformat()

    # -- saving -----------------------------------------------------------------

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> Learner:
        d = dict(d)
        d["concepts"] = {k: ConceptState(**v) for k, v in d.get("concepts", {}).items()}
        d["steps"] = {k: StepRecord(**v) for k, v in d.get("steps", {}).items()}
        d["bosses"] = {k: BossRecord(**v) for k, v in d.get("bosses", {}).items()}
        return cls(**d)
