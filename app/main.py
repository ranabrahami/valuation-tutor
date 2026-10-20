"""Valuation Tutor: Streamlit app.

    streamlit run app/main.py

Two pages: Learn (the game: stages, levels, bosses) and Explore (any company's
charts with their explanations). All text comes from locale files and the
sector module; views/ lays it out, ui.py draws the components.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))   # so `import ui`, `shared`, `views` work however it's launched
import shared  # noqa: E402
import ui  # noqa: E402
from views import explore, learn  # noqa: E402

st.set_page_config(page_title="Read the Numbers", page_icon=":material/insights:", layout="wide")

t = shared.load().t
ui.inject_css(t.direction)
page = st.navigation([
    st.Page(learn.render, title=t.t("game.learn"), icon=":material/school:", url_path="learn", default=True),
    st.Page(explore.render, title=t.t("game.explore"), icon=":material/insights:", url_path="explore"),
], position="top")
page.run()
