"""Valuation Tutor: Streamlit app.

    streamlit run app/main.py

Milestone 1: explore one company's charts, each with three explanation layers
(how to read it, what's normal in this sector, what this company's chart shows).
All text comes from the locale files and the sector module; ui.py draws it.
"""

import sys
from pathlib import Path

import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).parent))   # so `import ui` works however the app is launched
import ui  # noqa: E402

from valuation_tutor.core.explain import ExplainedChart, Explainer  # noqa: E402
from valuation_tutor.core.i18n import Translator  # noqa: E402
from valuation_tutor.core.registry import load_sectors, load_settings  # noqa: E402

st.set_page_config(page_title="Read the Numbers", page_icon=":material/insights:", layout="wide")

SECTIONS = {
    "story": ("app.section_story", "app.section_story_intro", ["revenue_trend", "margins", "profit_vs_cash", "sbc"]),
    "peers": ("app.section_peers", "app.section_peers_intro", ["peers_ev_revenue", "peer_fit"]),
    "value": ("app.section_value", "app.section_value_intro", ["price_vs_value", "implied_growth", "sensitivity"]),
}


@st.cache_resource(show_spinner="Loading company data...")
def load(locale: str):
    settings = load_settings()
    sectors = load_sectors({**settings, "locale": locale})
    t = Translator(locale)
    return settings, sectors, t, {sid: Explainer(s, t) for sid, s in sectors.items()}


@st.cache_resource(show_spinner=False)
def company_data(sector_id: str, ticker: str, locale: str):
    return load(locale)[1][sector_id].company_data(ticker)


settings, sectors, t, explainers = load(load_settings()["locale"])
ui.inject_css(t.direction)


# ---------------------------------------------------------------------------
# App bar: brand, sector and company
# ---------------------------------------------------------------------------

bar = st.columns([5, 2, 2], vertical_alignment="center")
with bar[0]:
    ui.brand(t.t("app.title"))
sector_id = bar[1].selectbox(t.t("app.sector"), list(sectors), format_func=lambda s: sectors[s].name,
                             label_visibility="collapsed")
sector, explainer = sectors[sector_id], explainers[sector_id]
companies = {c.ticker: c for c in sector.companies()}
default = sector.teaching_examples().get("default", next(iter(companies)))
ticker = bar[2].selectbox(t.t("app.company"), list(companies), index=list(companies).index(default),
                          format_func=lambda tk: companies[tk].name, label_visibility="collapsed")
ref = companies[ticker]
data = company_data(sector_id, ticker, settings["locale"])

ui.company_header(ref, data.headline(sector.headline_metrics()), explainer.fmt)
st.write("")


# ---------------------------------------------------------------------------
# One chart card
# ---------------------------------------------------------------------------

def chart_card(e: ExplainedChart) -> None:
    cid = e.chart.id
    with st.container(key=f"card_{cid}"):
        head = st.columns([6, 1.7, 1.3], vertical_alignment="center")
        head[0].subheader(e.chart.title, anchor=False)
        if not e.available:
            st.info(t.t("app.unavailable", company=ref.name), icon=":material/info:")
            return
        g = e.guide
        with head[1].popover(t.t("app.how_to_read_short"), icon=":material/menu_book:", width="stretch"):
            st.html(ui.guide([("eye", t.t("app.axes"), g.axes), ("spark", t.t("app.look_first"), g.look_first),
                              ("check", t.t("app.good"), g.good), ("alert", t.t("app.worrying"), g.worrying)]))
        with head[2].popover(t.t("app.sources_short"), icon=":material/link:", width="stretch"):
            fmt = explainer.fmt
            st.dataframe(pd.DataFrame([{t.t("app.col_number"): f.label, t.t("app.col_period"): f.period,
                                        t.t("app.col_value"): fmt.fact(f),
                                        t.t("app.col_source"): f.source + (f" ({f.note})" if f.note else "")}
                                       for f in e.facts]), hide_index=True, width=720)

        left, right = st.columns([7, 5], gap="large")
        with left:
            st.altair_chart(e.figure, width="stretch", theme=None)
        with right:
            st.html(ui.look_first(t.t("app.look_first"), g.look_first)
                    + ui.observations(t.t("app.this_company", company=ref.name), e.observations))
        st.html(ui.sector_notes(t.t("app.in_sector", sector=sector.name), e.sector_notes))

        if e.terms:
            names = {c.id: c for c in e.terms}
            picked = st.pills(t.t("app.terms"), list(names), format_func=lambda c: names[c].name,
                              key=f"terms_{cid}_{ticker}")
            if picked:
                c = names[picked]
                st.html(ui.term(c.name, c.plain, c.analogy))
    st.write("")


# ---------------------------------------------------------------------------
# Sections
# ---------------------------------------------------------------------------

section = st.segmented_control(
    t.t("app.section"), list(SECTIONS), default="story", key="section", label_visibility="collapsed",
    format_func=lambda s: t.t(SECTIONS[s][0])) or "story"
title_key, intro_key, chart_ids = SECTIONS[section]
st.html(f'<p class="rn-section-intro">{t.t(intro_key, company=ref.name)}</p>')
for chart_id in chart_ids:
    if chart_id in explainer.charts:
        chart_card(explainer.explain(data, chart_id))

ui.footer(t.t("app.data_as_of", date=sector.data_as_of, standard=sector.accounting_standard)
          + " · " + t.t("app.not_advice"))
