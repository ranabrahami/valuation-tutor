"""Loaded once per server: sectors, explainers, paths, question makers.

Also the per-browser-session learner (session state for now; milestone 4
saves it to a database for signed-in learners).
"""

from __future__ import annotations

from dataclasses import dataclass

import streamlit as st

from valuation_tutor.core.explain import Explainer
from valuation_tutor.core.i18n import Translator
from valuation_tutor.core.learner import Learner
from valuation_tutor.core.path import LearningPath
from valuation_tutor.core.quiz import QuizMaker
from valuation_tutor.core.registry import load_sectors, load_settings
from valuation_tutor.core.sector import CompanyData, SectorModule


@dataclass
class Bundle:
    settings: dict
    t: Translator
    sectors: dict[str, SectorModule]
    explainers: dict[str, Explainer]
    paths: dict[str, LearningPath]
    quizzes: dict[str, QuizMaker]


@st.cache_resource(show_spinner="Loading company data...")
def load() -> Bundle:
    settings = load_settings()
    sectors = load_sectors(settings)
    t = Translator(settings["locale"])
    explainers = {sid: Explainer(s, t) for sid, s in sectors.items()}
    return Bundle(settings, t, sectors, explainers, {sid: LearningPath(s) for sid, s in sectors.items()},
                  {sid: QuizMaker(e) for sid, e in explainers.items()})


@st.cache_resource(show_spinner=False)
def company_data(sector_id: str, ticker: str) -> CompanyData:
    return load().sectors[sector_id].company_data(ticker)


def data_for(sector_id: str):
    return lambda ticker: company_data(sector_id, ticker)


@st.cache_resource(show_spinner=False)
def step_questions(sector_id: str, step_id: str, company: str):
    b = load()
    step = b.paths[sector_id].step(step_id)
    if company != step.company:
        from dataclasses import replace
        step = replace(step, company=company)
    return b.quizzes[sector_id].for_step(step, data_for(sector_id), seed=step_id)


@st.cache_resource(show_spinner=False)
def boss_questions(sector_id: str, stage_id: str, attempt: int):
    b = load()
    path = b.paths[sector_id]
    stage = next(s for s in path.stages if s.id == stage_id)
    return b.quizzes[sector_id].boss(stage, data_for(sector_id), attempt, {s.company for s in stage.steps})


def learner() -> Learner:
    if "learner" not in st.session_state:
        st.session_state.learner = Learner()
    return st.session_state.learner


def sector_id() -> str:
    b = load()
    return st.session_state.setdefault("sector", next(iter(b.sectors)))


# ---------------------------------------------------------------------------
# The AI tutor (optional: without a key the app uses the written explanations)
# ---------------------------------------------------------------------------

def _api_key() -> str | None:
    import os

    from dotenv import load_dotenv
    from valuation_tutor.core.registry import PROJECT_ROOT
    load_dotenv(PROJECT_ROOT / ".env")
    if os.getenv("ANTHROPIC_API_KEY"):
        return os.environ["ANTHROPIC_API_KEY"]
    try:
        return st.secrets.get("ANTHROPIC_API_KEY")
    except Exception:              # no secrets file: running locally without a key
        return None


@st.cache_resource(show_spinner=False)
def tutors() -> dict:
    """One Tutor per sector (each formats numbers in its own currency), or {} without a key."""
    key = _api_key()
    if not key:
        return {}
    import anthropic

    from valuation_tutor.core.registry import PROJECT_ROOT
    from valuation_tutor.core.tutor import Tutor
    from valuation_tutor.core.tutor.store import SQLiteStore
    b = load()
    cfg = b.settings["tutor"]
    client = anthropic.Anthropic(api_key=key)
    store = SQLiteStore(PROJECT_ROOT / cfg["store_path"])
    language = b.t.get("meta.name") or "English"
    return {sid: Tutor(client, cfg, store, b.explainers[sid].fmt, language) for sid in b.sectors}


def tutor(sector_id: str):
    # Tests put a Tutor backed by a fake client here, so the UI can be tested without a key.
    if "tutor_override" in st.session_state:
        return st.session_state.tutor_override
    return tutors().get(sector_id)


def learner_id() -> str:
    """Anonymous per-session id for the daily caps (a hashed account id from milestone 4)."""
    import uuid
    return st.session_state.setdefault("learner_id", uuid.uuid4().hex)
