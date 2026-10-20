"""Game rules and the learner model: pure Python, no data needed."""

from datetime import date

from valuation_tutor.core import game
from valuation_tutor.core.learner import Learner


def test_mastery_needs_two_correct_in_a_row_on_different_questions():
    l = Learner()
    l.answer(["growth"], True, "trend_growth_direction:HUBS", first_try=True)
    assert not l.mastered("growth")
    l.answer(["growth"], True, "trend_growth_direction:HUBS", first_try=True)   # same question again
    assert not l.mastered("growth")
    out = l.answer(["growth"], True, "concept:growth", first_try=True)
    assert l.mastered("growth") and out.newly_mastered == ["growth"]


def test_a_mistake_resets_the_streak_and_picks_a_new_explanation_style():
    l = Learner()
    l.answer(["margin"], True, "a", True)
    out = l.answer(["margin"], False, "b", True)
    assert l.concept("margin").streak == 0 and l.concept("margin").struggles == 1
    assert out.next_style == "plain" and out.xp == 0
    assert l.answer(["margin"], False, "b", False).next_style == "analogy"
    assert l.struggle(["margin"]) == "other_company"
    assert l.struggle(["margin"]) == "prerequisite"
    assert l.struggle(["margin"]) == "prerequisite"            # stays on the last style


def test_xp_rewards_understanding_not_speed():
    l = Learner()
    l.answer(["revenue"], True, "a", first_try=True)
    l.answer(["revenue"], True, "b", first_try=False)
    l.answer(["revenue"], False, "c", first_try=True)
    assert l.xp == game.XP_CORRECT_FIRST_TRY + game.XP_CORRECT_AFTER_RETRY
    assert l.write_observation("revenue", "too short") == 0
    assert l.write_observation("revenue", "the bars go up every single year") == game.XP_OBSERVATION
    assert l.write_observation("revenue", "the bars go up every single year again") == 0   # only once


def test_stars():
    l = Learner()
    assert l.complete_step("revenue", right_first_time=False) == 1
    l.write_observation("growth", "growth numbers are getting smaller each year")
    assert l.complete_step("growth", right_first_time=True) == 3
    assert l.complete_step("growth", right_first_time=False) == 2 and l.step("growth").stars == 3   # best kept


def test_badges_follow_mastery():
    l = Learner()
    for cid in ("profit", "free_cash_flow"):
        l.answer([cid], True, "a", True)
    out = l.answer(["profit", "free_cash_flow"], True, "b", True)
    assert "cash_detective" in out.new_badges and "cash_detective" in l.badges


def test_bosses_promote_and_give_hints_once():
    l = Learner()
    assert l.rank == "intern"
    assert not l.finish_boss("story", 1)
    assert l.finish_boss("story", 2) and l.rank == "analyst"
    assert l.hints == game.STARTING_HINTS + game.HINTS_PER_BOSS
    l.finish_boss("story", 3)                                 # replaying doesn't pay out again
    assert l.hints == game.STARTING_HINTS + game.HINTS_PER_BOSS and l.boss("story").best == 3


def test_hints_run_out():
    l = Learner(hints=1)
    assert l.use_hint() and not l.use_hint()


def test_streak_with_one_free_freeze():
    l = Learner()
    l.touch(date(2026, 10, 1)); l.touch(date(2026, 10, 2))
    assert l.streak_days == 2
    l.touch(date(2026, 10, 4))                                # missed one day: freeze used
    assert l.streak_days == 3 and not l.freeze_available
    l.touch(date(2026, 10, 6))                                # missed again: streak restarts
    assert l.streak_days == 1


def test_round_trips_through_a_dict():
    l = Learner()
    l.answer(["growth"], True, "a", True)
    l.write_observation("growth", "growth numbers are getting smaller each year")
    l.finish_boss("story", 3)
    assert Learner.from_dict(l.to_dict()) == l


def test_tutor_verdict_overrides_the_word_count_for_the_third_star():
    l = Learner()
    l.write_observation("revenue", "the bars are blue and there are five of them")   # long but off the point
    l.judge_observation("revenue", False)
    assert l.complete_step("revenue", right_first_time=True) == 2
    l.write_observation("growth", "slower")                                           # short but right
    l.judge_observation("growth", True)
    assert l.complete_step("growth", right_first_time=True) == 3
