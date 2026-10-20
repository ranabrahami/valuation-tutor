"""The Streamlit app: headless (AppTest) and in a real browser (Playwright + Chrome).

AppTest runs the Python; only the browser test catches chart specs that fail
to draw, or text that renders wrongly (e.g. "$" read as a maths formula).
Both need the engine's data, so they're skipped without it.
"""

import socket
import subprocess
import sys
import time
from pathlib import Path

import pytest

pytest.importorskip("saas_valuation")
from saas_valuation.config import load_config, project_path  # noqa: E402
from streamlit.testing.v1 import AppTest  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / "app" / "main.py"
pytestmark = pytest.mark.skipif(
    not (project_path(load_config()["data"]["processed_dir"]) / "comps.csv").exists(),
    reason="engine data not built")


def html(at) -> str:
    return " ".join(e.proto.body for e in at.get("html"))


def questions(at):
    """The questions of the level in progress (app/ is on sys.path once the app has run)."""
    import shared
    a = at.session_state["activity"]
    return shared.step_questions("saas", a["id"], a["company"])


def test_learn_flow_from_map_to_level_complete():
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    assert "Intern" in html(at) and "Mystery company" in html(at)
    at.button(key="continue").click().run()                      # start level 1
    assert "Reading a revenue chart" in html(at)
    at.text_area(key="obs_revenue").input("The bars rise every year and the last is the tallest").run()
    at.button(key="show_me").click().run()
    assert "What this shows for Adobe" in html(at)
    at.button(key="to_check").click().run()
    lr = at.session_state["learner"]
    for _ in range(5):                                           # answer every question correctly
        if "next_q" in [b.key for b in at.button]:
            at.button(key="next_q").click().run()
            continue
        if not at.radio:
            break
        q = questions(at)[at.session_state["activity"]["q"]]
        at.radio[0].set_value(q.answer).run()
        at.button(key="submit").click().run()
    assert not at.exception, at.exception
    assert lr.step("revenue").completed and lr.step("revenue").stars == 3
    assert "Level complete" in html(at) and lr.xp > 0


def test_mistake_unlocks_a_different_explanation():
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    at.button(key="continue").click().run()
    at.button(key="skip_obs").click().run()
    at.button(key="to_check").click().run()
    q = questions(at)[0]
    at.radio[0].set_value(next(i for i in range(len(q.options)) if i != q.answer)).run()
    at.button(key="submit").click().run()
    assert "Not quite" in html(at) and "try it another way" in html(at)
    assert at.session_state["learner"].concept(q.concepts[0]).struggles == 1


@pytest.fixture(scope="module")
def app_url():
    with socket.socket() as s:
        s.bind(("localhost", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "streamlit", "run", str(APP), "--server.headless", "true",
                             "--server.port", str(port)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    for _ in range(60):
        try:
            socket.create_connection(("localhost", port), timeout=1).close()
            break
        except OSError:
            time.sleep(0.5)
    yield f"http://localhost:{port}"
    proc.terminate()
    proc.wait(timeout=10)


def test_page_renders_in_a_real_browser(app_url):
    sync_api = pytest.importorskip("playwright.sync_api")
    errors = []
    with sync_api.sync_playwright() as p:
        try:
            browser = p.chromium.launch(channel="chrome")
        except Exception as exc:
            pytest.skip(f"Google Chrome unavailable: {exc}")
        page = browser.new_page(viewport={"width": 1500, "height": 1000})
        page.on("pageerror", lambda e: errors.append(str(e)))
        page.goto(app_url)                                      # Learn: the map
        page.wait_for_selector(".rn-rank", timeout=90_000)
        page.goto(f"{app_url}/explore")
        page.wait_for_selector('[data-testid="stVegaLiteChart"]', timeout=90_000)
        page.wait_for_timeout(4_000)
        charts = page.locator('[data-testid="stVegaLiteChart"]').count()
        text = page.locator('[data-testid="stMain"]').inner_text()
        maths = page.locator(".katex").count()
        icons = page.evaluate("() => getComputedStyle(document.querySelector('.rn-i')).maskImage")
        browser.close()
    assert not errors, errors
    assert charts == 4                       # the "business story" section
    assert maths == 0, "a $ amount was rendered as a formula"
    assert "$3.1B in FY2025" in text
    assert icons.startswith("url(")             # icon CSS survived the HTML sanitizer
