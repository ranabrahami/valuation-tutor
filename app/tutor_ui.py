"""Tutor pieces shared by the Learn and Explore pages.

Every tutor call is wrapped so that, when the tutor can't help (no key, daily
cap, budget, refusal, an answer it couldn't ground), the learner sees a short
note and the written explanation instead of an error.
"""

from __future__ import annotations

import shared
import streamlit as st
import ui

from valuation_tutor.core.tutor import Unavailable
from valuation_tutor.core.tutor.context import TutorContext, context_for


def language() -> str:
    return shared.load().t.get("meta.name") or "English"


def chart_context(data, chart_id: str, lesson: dict | None = None) -> TutorContext:
    b, sid = shared.load(), shared.sector_id()
    return context_for(b.explainers[sid], data, chart_id, shared.learner(), lesson, language())


def reason_note(reason: str) -> str:
    t = shared.load().t
    return ui.feedback("info", t.t("tutor.name"), t.t(f"tutor.reasons.{reason}"))


def reply_html(ctx: TutorContext, text: str, tags: list[str], who: str | None = None) -> str:
    b, sid = shared.load(), shared.sector_id()
    known = ctx.tags()
    sources = [(tag, known[tag]) for tag in tags if tag in known]
    return ui.tutor_reply(who or b.t.t("tutor.name"), text, sources, b.explainers[sid].fmt, b.t.t("tutor.sources"))


def call(fn, *args):
    """Run a tutor method; returns (reply, None) or (None, reason)."""
    try:
        return fn(*args), None
    except Unavailable as u:
        return None, u.reason


def ask_box(key: str, ctx: TutorContext) -> None:
    """A small chat about the chart on screen. History lives in the session."""
    b, sid = shared.load(), shared.sector_id()
    t, tutor = b.t, shared.tutor(sid)
    if tutor is None:
        st.caption(t.t("tutor.switched_off"))
        return
    history = st.session_state.setdefault(f"chat_{key}", [])
    for who, msg, tags in history:
        if who == "learner":
            st.html(ui.my_message(msg))
        elif who == "tutor":
            st.html(reply_html(ctx, msg, tags))
        else:
            st.html(reason_note(msg))
    with st.form(key=f"ask_{key}", clear_on_submit=True, border=False):
        cols = st.columns([5, 1], vertical_alignment="bottom")
        question = cols[0].text_input(t.t("tutor.ask_title"), placeholder=t.t("tutor.ask_placeholder"),
                                      label_visibility="collapsed")
        sent = cols[1].form_submit_button(t.t("tutor.ask"), type="primary", width="stretch")
    if sent and question.strip():
        with st.spinner(t.t("tutor.thinking")):
            past = [(("Learner" if w == "learner" else "Tutor"), m) for w, m, _ in history if w != "note"]
            reply, reason = call(tutor.answer, ctx, question.strip(), past, shared.learner_id())
        history.append(("learner", question.strip(), []))
        history.append(("tutor", reply.text, [tag for tag, _ in reply.sources]) if reply else ("note", reason, []))
        st.rerun()
