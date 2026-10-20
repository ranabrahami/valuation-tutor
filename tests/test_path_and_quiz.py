"""The learning path and question generators, on the fake sector and on SaaS."""

import pytest
from fake_sector import FakeSector

from valuation_tutor.core import game
from valuation_tutor.core.explain import Explainer
from valuation_tutor.core.i18n import Translator
from valuation_tutor.core.learner import Learner
from valuation_tutor.core.path import LearningPath
from valuation_tutor.core.quiz import GENERATORS, QuizMaker


def maker(sector):
    cache = {}
    return QuizMaker(Explainer(sector, Translator())), lambda t: cache.setdefault(t, sector.company_data(t))


def test_fake_sector_path_uses_its_own_step_and_charts():
    path = LearningPath(FakeSector())
    ids = [s.id for s in path.steps]
    assert ids.index("same_store_sales") == ids.index("growth") + 1
    sss = path.step("same_store_sales")
    assert sss.sector == "fake" and sss.lesson["title"] == "Same-store sales" and sss.chart_id == "sales"
    assert path.step("cash").chart_id == "cash"


def test_unlocking_order():
    path, l = LearningPath(FakeSector()), Learner()
    story, business = path.stages[0], path.stages[1]
    first, second = story.steps[0], story.steps[1]
    assert path.step_unlocked(l, first) and not path.step_unlocked(l, second)
    assert not path.boss_unlocked(l, story) and not path.stage_unlocked(l, business)
    for s in story.steps:
        l.complete_step(s.id, True)
    assert path.boss_unlocked(l, story) and path.next_up(l) == ("boss", "story")
    l.finish_boss("story", 3)
    assert path.stage_unlocked(l, business) and path.next_up(l) == ("step", business.steps[0].id)


def test_mastered_steps_can_be_skipped():
    path, l = LearningPath(FakeSector()), Learner()
    step = path.step("growth")
    assert not path.skippable(l, step)
    l.concept("growth").mastered = True
    assert path.skippable(l, step)


def test_every_fake_step_has_a_question_and_answers_are_valid():
    sector = FakeSector()
    qm, data_for = maker(sector)
    for step in LearningPath(sector).steps:
        qs = qm.for_step(step, data_for)
        assert qs, step.id
        for q in qs:
            assert 0 <= q.answer < len(q.options) and len(set(q.options)) == len(q.options)
            assert "{" not in q.prompt + q.why


def test_boss_hides_the_company_name():
    sector = FakeSector()
    qm, data_for = maker(sector)
    stage = LearningPath(sector).stages[0]
    ticker, qs = qm.boss(stage, data_for, attempt=0, exclude=set())
    name = sector.company_data(ticker).ref.name
    assert len(qs) == game.BOSS_QUESTIONS
    assert all(name not in q.prompt + q.why + " ".join(q.options) for q in qs)


saas = pytest.importorskip("valuation_tutor.sectors.saas")


@pytest.fixture(scope="module")
def saas_setup():
    pytest.importorskip("saas_valuation")
    sector = saas.SaasSector()
    try:
        sector.engine
    except FileNotFoundError:
        pytest.skip("engine data not built")
    return sector, LearningPath(sector), *maker(sector)


def test_saas_path_inserts_its_steps(saas_setup):
    _, path, _, _ = saas_setup
    ids = [s.id for s in path.steps]
    assert ids.index("sbc") == ids.index("margins") + 1
    assert ids.index("growth_premium") == ids.index("multiples") + 1
    assert [st.id for st in path.stages] == ["story", "business", "peers", "value", "beliefs"]


def test_saas_questions_are_answered_by_the_data(saas_setup):
    sector, path, qm, data_for = saas_setup
    qs = {q.variant: q for step in path.steps for q in qm.for_step(step, data_for)}

    def right(variant):
        q = qs[variant]
        return q.options[q.answer]

    assert right("trend_peak:ADBE") == "FY2025"                    # Adobe grew every year
    assert right("cash_vs_profit:DDOG") == "Free cash flow"        # a loss on paper, cash in the bank
    assert right("implied_vs_actual:CRWD") == "Faster"             # the price needs far faster growth
    assert right("implied_vs_actual:HUBS") == "Slower"             # capstone default company
    assert right("fit_side:HUBS").startswith("Below")


def test_every_saas_boss_builds_and_varies(saas_setup):
    _, path, qm, data_for = saas_setup
    for stage in path.stages:
        exclude = {s.company for s in stage.steps}
        companies = {qm.boss(stage, data_for, a, exclude)[0] for a in range(3)}
        assert not companies & exclude and len(companies) >= 2


def test_every_generator_is_used_somewhere():
    from valuation_tutor.core.quiz import BY_KIND
    assert {g for gens in BY_KIND.values() for g in gens} == set(GENERATORS)
