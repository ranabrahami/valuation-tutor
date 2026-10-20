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


def test_app_runs_and_switches_company():
    at = AppTest.from_file(str(APP), default_timeout=120)
    at.run()
    assert not at.exception, at.exception
    html = lambda: " ".join(e.proto.body for e in at.get("html"))   # noqa: E731
    assert "<h1>HubSpot</h1>" in html()
    at.selectbox[1].set_value("DDOG").run()
    assert not at.exception
    assert "<h1>Datadog</h1>" in html()
    assert "loss" in html()                       # DDOG: a loss on paper, cash in the bank
    at.segmented_control(key="section").set_value("value").run()
    assert not at.exception and "price" in html()


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
        page.goto(app_url)
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
