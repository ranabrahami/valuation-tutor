"""Valuation Tutor: Streamlit app.

    streamlit run app/main.py

Pages: Learn (the game), Explore (any company's charts), Progress, About.
All text comes from locale files and the sector module; views/ lays it out,
ui.py draws the components. Progress is saved after every run for signed-in
learners.
"""

import sys
from pathlib import Path

import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))   # so `import ui`, `shared`, `views` work however it's launched
import account_ui  # noqa: E402
import shared  # noqa: E402
import ui  # noqa: E402
from views import about, explore, learn, progress  # noqa: E402

st.set_page_config(page_title="Read the Numbers", page_icon=":material/insights:", layout="wide")

t = shared.load().t
ui.inject_css(t.direction)
page = st.navigation([
    st.Page(learn.render, title=t.t("game.learn"), icon=":material/school:", url_path="learn", default=True),
    st.Page(explore.render, title=t.t("game.explore"), icon=":material/insights:", url_path="explore"),
    st.Page(progress.render, title=t.t("progress.nav"), icon=":material/military_tech:", url_path="progress"),
    st.Page(about.render, title=t.t("about.nav"), icon=":material/info:", url_path="about"),
], position="top")
if shared.auth_configured():
    with st.container(key="account_bar"):
        account_ui.control(st)
page.run()
shared.save_progress()
