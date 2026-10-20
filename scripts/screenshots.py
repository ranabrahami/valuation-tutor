"""Capture the README screenshots from a running app.

    streamlit run app/main.py --server.port 8510      # in one terminal
    python scripts/screenshots.py                      # in another; writes docs/images/*.png

Plays the first level and boss as a guest, so it needs no sign-in and no API
key (the tutor isn't shown). Uses the locally installed Google Chrome.
"""

import argparse
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

OUT = Path(__file__).resolve().parents[1] / "docs" / "images"


def settle(page: Page, ms: int = 2500) -> None:
    page.wait_for_timeout(ms)


def click(page: Page, name: str) -> None:
    page.get_by_role("button", name=name).first.click()
    settle(page)


def scroll(page: Page, y: int) -> None:
    page.evaluate(f"document.querySelector('[data-testid=\"stMain\"]').scrollTo(0, {y})")
    settle(page, 800)


def answer(page: Page, index: int) -> None:
    page.locator('[data-testid="stRadio"] [role="radiogroup"] label').nth(index).click()
    settle(page, 800)
    click(page, "Check answer")


def main(url: str) -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome")
        page = browser.new_page(viewport={"width": 1440, "height": 900}, device_scale_factor=1.5)
        page.goto(url)
        page.wait_for_selector(".rn-rank", timeout=120_000)
        settle(page)
        page.screenshot(path=OUT / "map.png")

        click(page, "Start")
        page.locator("textarea").fill("The bars get taller every year, so sales keep growing")
        settle(page, 600)
        page.screenshot(path=OUT / "look.png")
        click(page, "Show me")
        page.screenshot(path=OUT / "learn.png")
        click(page, "Check your understanding")
        answer(page, 1)                                   # a wrong answer, to show the re-explanation
        page.screenshot(path=OUT / "mistake.png")

        page.goto(f"{url}/explore")
        page.wait_for_selector('[data-testid="stVegaLiteChart"]', timeout=120_000)
        settle(page)
        page.screenshot(path=OUT / "explore.png")
        page.goto(f"{url}/progress")
        page.wait_for_selector(".rn-badges", timeout=60_000)
        settle(page)
        page.screenshot(path=OUT / "progress.png")
        browser.close()
    for f in sorted(OUT.glob("*.png")):
        print(f"wrote {f.relative_to(OUT.parents[1])}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--url", default="http://localhost:8510")
    main(parser.parse_args().url)
