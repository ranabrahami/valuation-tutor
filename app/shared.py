"""Loaded once per server: sectors, explainers, paths, question makers.

Also the per-browser-session learner (session state for now; milestone 4
saves it to a database for signed-in learners).
"""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass

import streamlit as st

from valuation_tutor.core.explain import Explainer
from valuation_tutor.core.i18n import Translator
from valuation_tutor.core.learner import Learner
from valuation_tutor.core.path import LearningPath
from valuation_tutor.core.quiz import QuizMaker
from valuation_tutor.core.registry import PROJECT_ROOT, load_sectors, load_settings
from valuation_tutor.core.sector import CompanyData, SectorModule
from valuation_tutor.core.storage import SQLStore


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
    """This session's learner. Signed in: loaded from the database (guest progress merged in)."""
    acct = account()
    if acct and st.session_state.get("learner_owner") != acct["id"]:
        saved = store().load_learner(acct["id"])
        mine = Learner.from_dict(saved) if saved else Learner()
        if "learner" in st.session_state and st.session_state.get("learner_owner") is None:
            mine.merge(st.session_state.learner)            # what they did as a guest isn't lost
        st.session_state.learner, st.session_state.learner_owner = mine, acct["id"]
    if "learner" not in st.session_state:
        st.session_state.learner, st.session_state.learner_owner = Learner(), None
    return st.session_state.learner


def save_progress() -> None:
    """Called after every run; writes only when something changed."""
    acct = account()
    if not acct or "learner" not in st.session_state:
        return
    data = st.session_state.learner.to_dict()
    digest = hash(json.dumps(data, sort_keys=True))
    if st.session_state.get("saved_digest") != digest:
        store().save_learner(acct["id"], data)
        st.session_state.saved_digest = digest


def sector_id() -> str:
    b = load()
    return st.session_state.setdefault("sector", next(iter(b.sectors)))


# ---------------------------------------------------------------------------
# The AI tutor (optional: without a key the app uses the written explanations)
# ---------------------------------------------------------------------------

def secret(name: str) -> str | None:
    """From the environment (or .env) first, then Streamlit secrets (how the deployed app gets them)."""
    from dotenv import load_dotenv
    load_dotenv(PROJECT_ROOT / ".env")
    if os.getenv(name):
        return os.environ[name]
    try:
        value = st.secrets.get(name)
    except Exception:              # no secrets file: running locally
        return None
    return str(value) if value else None


@st.cache_resource(show_spinner=False)
def store() -> SQLStore:
    url = secret("DATABASE_URL") or load().settings["database_url"]
    if url.startswith("sqlite:///") and not url.startswith("sqlite:////"):
        url = f"sqlite:///{PROJECT_ROOT / url.removeprefix('sqlite:///')}"   # relative to the project
        (PROJECT_ROOT / "data").mkdir(exist_ok=True)
    return SQLStore(url)


def auth_configured() -> bool:
    try:
        return "auth" in st.secrets
    except Exception:
        return False


def account() -> dict | None:
    """{"id": opaque key, "name": first name} for a signed-in learner, else None.

    The key is a salted hash of the provider's subject id: the database never
    holds an email address or anything that identifies the person directly.
    """
    if not auth_configured() or not st.user.is_logged_in:
        return None
    return account_from(dict(st.user), secret("USER_ID_SALT") or "local-development-salt")


def account_from(user: dict, salt: str) -> dict:
    subject = f"{user.get('iss', '')}|{user.get('sub') or user.get('email')}"
    return {"id": hashlib.sha256(f"{salt}|{subject}".encode()).hexdigest(),
            "name": user.get("given_name") or user.get("name") or ""}


def _api_key() -> str | None:
    return secret("ANTHROPIC_API_KEY")


@st.cache_resource(show_spinner=False)
def tutors() -> dict:
    """One Tutor per sector (each formats numbers in its own currency), or {} without a key."""
    key = _api_key()
    if not key:
        return {}
    import anthropic

    from valuation_tutor.core.tutor import Tutor
    b = load()
    client = anthropic.Anthropic(api_key=key)
    language = b.t.get("meta.name") or "English"
    return {sid: Tutor(client, b.settings["tutor"], store(), b.explainers[sid].fmt, language) for sid in b.sectors}


def tutor(sector_id: str):
    # Tests put a Tutor backed by a fake client here, so the UI can be tested without a key.
    if "tutor_override" in st.session_state:
        return st.session_state.tutor_override
    return tutors().get(sector_id)


def learner_id() -> str:
    """Who the tutor's daily cap applies to: the account if signed in, else this session."""
    import uuid
    acct = account()
    return acct["id"] if acct else st.session_state.setdefault("learner_id", uuid.uuid4().hex)
