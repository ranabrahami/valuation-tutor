"""Valuation Tutor: Streamlit app.

    streamlit run app/main.py

Milestone 1: explore one company's charts, each with three explanation layers
(how to read it, what's normal in this sector, what this company's chart shows).
All text comes from the locale files and the sector module; this file only lays
it out.
"""

import pandas as pd
import streamlit as st

from valuation_tutor.core.explain import ExplainedChart, Explainer
from valuation_tutor.core.i18n import Translator
from valuation_tutor.core.registry import load_sectors, load_settings

st.set_page_config(page_title="Read the Numbers", layout="wide")

TONE_ICON = {"good": "✅", "warning": "⚠️", "neutral": "•"}


def md(text: str) -> str:
    """Escape dollar signs: Streamlit markdown reads $...$ as a maths formula."""
    return text.replace("$", "\\$")
SECTIONS = [
    ("app.section_story", ["revenue_trend", "margins", "profit_vs_cash", "sbc"]),
    ("app.section_peers", ["peers_ev_revenue", "peer_fit"]),
    ("app.section_value", ["price_vs_value", "implied_growth", "sensitivity"]),
]


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
if t.direction == "rtl":
    st.markdown("<style>.stApp {direction: rtl; text-align: right;}</style>", unsafe_allow_html=True)


# ---------------------------------------------------------------------------
# Sidebar: choose a sector and a company
# ---------------------------------------------------------------------------

st.sidebar.title(t.t("app.title"))
st.sidebar.caption(t.t("app.tagline"))
sector_id = st.sidebar.selectbox(t.t("app.sector"), list(sectors), format_func=lambda s: sectors[s].name)
sector, explainer = sectors[sector_id], explainers[sector_id]
companies = {c.ticker: c for c in sector.companies()}
default = sector.teaching_examples().get("default", next(iter(companies)))
ticker = st.sidebar.selectbox(t.t("app.company"), list(companies), index=list(companies).index(default),
                              format_func=lambda tk: companies[tk].name)
ref = companies[ticker]
st.sidebar.markdown(f"**{t.t('app.profile')}:** {ref.profile_label}")
st.sidebar.caption(t.t("app.data_as_of", date=sector.data_as_of, standard=sector.accounting_standard))
st.sidebar.caption(t.t("app.not_advice"))


# ---------------------------------------------------------------------------
# One chart with its three explanation layers
# ---------------------------------------------------------------------------

def show_chart(e: ExplainedChart, first: bool) -> None:
    st.subheader(e.chart.title)
    if not e.available:
        st.info(t.t("app.unavailable", company=ref.name))
        return
    left, right = st.columns([3, 2], gap="large")
    with left:
        st.altair_chart(e.figure, width="stretch", theme=None)
    with right:
        st.markdown(f"**{t.t('app.this_company', company=ref.name)}**")
        for o in e.observations:
            st.markdown(f"{TONE_ICON[o.tone]} {md(o.text)}")
        if e.sector_notes:
            st.markdown(f"**{t.t('app.in_sector', sector=sector.name)}**")
            for note in e.sector_notes:
                st.caption(md(note))

    with st.expander(f"📖 {t.t('app.how_to_read')}", expanded=first):
        g = e.guide
        c1, c2 = st.columns(2)
        c1.markdown(f"**{t.t('app.axes')}**  \n{md(g.axes)}")
        c1.markdown(f"**{t.t('app.look_first')}**  \n{md(g.look_first)}")
        c2.markdown(f"**✅ {t.t('app.good')}**  \n{md(g.good)}")
        c2.markdown(f"**⚠️ {t.t('app.worrying')}**  \n{md(g.worrying)}")
    if e.terms:
        with st.expander(f"🏷️ {t.t('app.terms')}"):
            for c in e.terms:
                st.markdown(md(f"**{c.name}**: {c.plain}  \n*{c.analogy}*" if c.analogy else f"**{c.name}**: {c.plain}"))
    with st.expander(f"🔎 {t.t('app.sources')}"):
        fmt = explainer.fmt
        st.dataframe(pd.DataFrame([{"Number": f.label, "Period": f.period, "Value": fmt.fact(f),
                                    "Source": f.source + (f" ({f.note})" if f.note else "")} for f in e.facts]),
                     hide_index=True, width="stretch")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.title(t.t("app.explore"))
st.markdown(t.t("app.explore_intro"))
st.header(ref.name)

data = company_data(sector_id, ticker, settings["locale"])
first = True
for section_key, chart_ids in SECTIONS:
    present = [c for c in chart_ids if c in explainer.charts]
    if not present:
        continue
    st.divider()
    st.markdown(f"### {t.t(section_key)}")
    for chart_id in present:
        show_chart(explainer.explain(data, chart_id), first)
        first = False
