"""The tutor inside the app, with a fake Claude client (nothing billed)."""

from pathlib import Path

import pytest

pytest.importorskip("saas_valuation")
from saas_valuation.config import load_config, project_path  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402
from test_tutor import CFG, FakeClient  # noqa: E402

from valuation_tutor.core.fmt import Formatter  # noqa: E402
from valuation_tutor.core.i18n import Translator  # noqa: E402
from valuation_tutor.core.tutor import Tutor  # noqa: E402
from valuation_tutor.core.tutor.store import MemoryStore  # noqa: E402

APP = str(Path(__file__).resolve().parents[1] / "app" / "main.py")
pytestmark = pytest.mark.skipif(
    not (project_path(load_config()["data"]["processed_dir"]) / "comps.csv").exists(), reason="engine data not built")


def html(at) -> str:
    return " ".join(e.proto.body for e in at.get("html"))


def app_with(*replies):
    client = FakeClient(*replies)
    at = AppTest.from_file(APP, default_timeout=120)
    at.session_state["tutor_override"] = Tutor(client, CFG, MemoryStore(), Formatter("USD", Translator()))
    at.run()
    return at, client


def test_tutor_reads_the_observation_and_awards_the_star():
    at, client = app_with({"reply": "Yes, the bars rise every year [F1].", "verdict": "spot_on",
                           "credit_own_words": True})
    at.button(key="continue").click().run()
    at.text_area(key="obs_revenue").input("bars go up").run()          # short, but right
    at.button(key="show_me").click().run()
    assert not at.exception, at.exception
    page = html(at)
    assert "Spot on" in page and "the bars rise every year" in page and "<sup" in page   # source marker
    assert at.session_state["learner"].step("revenue").own_words is True
    assert "bars go up" in client.calls[0]["messages"][0]["content"][1]["text"]


def test_tutor_reexplains_after_a_mistake():
    at, client = app_with({"reply": "Think of each bar as a year of sales. Which one reaches highest?"})
    at.button(key="continue").click().run()
    at.button(key="skip_obs").click().run()
    at.button(key="to_check").click().run()
    import shared
    a = at.session_state["activity"]
    q = shared.step_questions("saas", a["id"], a["company"])[0]
    at.radio[0].set_value(next(i for i in range(len(q.options)) if i != q.answer)).run()
    at.button(key="submit").click().run()
    assert not at.exception, at.exception
    assert "Which one reaches highest?" in html(at)
    assert "<style>plain</style>" in client.calls[0]["messages"][0]["content"][1]["text"]
    at.run()                                                          # a rerun doesn't call again
    assert len(client.calls) == 1


def test_when_the_tutor_cannot_help_the_learner_sees_a_note_not_an_error():
    bad = {"reply": "Revenue was $99B.", "verdict": "partly", "credit_own_words": True}
    at, _ = app_with(bad, bad)                                        # ungrounded twice
    at.button(key="continue").click().run()
    at.text_area(key="obs_revenue").input("the bars go up every year").run()
    at.button(key="show_me").click().run()
    assert not at.exception, at.exception
    assert "only the numbers on screen" in html(at)
    assert at.session_state["learner"].step("revenue").own_words is None   # falls back to the word count
