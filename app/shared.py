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
