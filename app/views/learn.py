"""Learn: the stage map, the level player and the boss challenge.

All rules (unlocking, stars, XP, mastery, which explanation style comes next)
live in core/; this module only shows them and passes the learner's clicks back.
"""

from __future__ import annotations

import shared
import streamlit as st
import ui

from valuation_tutor.core import game
from valuation_tutor.core.path import Step
from valuation_tutor.core.quiz import mask

PHASES = ["game.your_turn", "game.explain", "game.check", "game.level_complete"]


def _rerun() -> None:
    st.rerun()


def lesson(step: Step, t) -> dict:
    return step.lesson or t.get(f"lessons.{step.id}") or {}


def start_step(step_id: str) -> None:
    path = shared.load().paths[shared.sector_id()]
    st.session_state.activity = {"type": "step", "id": step_id, "phase": 0, "q": 0, "tries": 0, "answered": None,
                                 "all_first": True, "hidden": [], "style": None, "company": path.step(step_id).company,
                                 "xp0": shared.learner().xp, "mastered": [], "badges": [], "seen": False}


def start_boss(stage_id: str) -> None:
    lr = shared.learner()
    st.session_state.activity = {"type": "boss", "stage": stage_id, "attempt": lr.boss(stage_id).attempts,
                                 "phase": "intro", "q": 0, "score": 0, "answered": None, "rank0": lr.rank,
                                 "xp0": lr.xp, "result": None}


def back_to_map() -> None:
    st.session_state.activity = None


# ---------------------------------------------------------------------------
# Map
# ---------------------------------------------------------------------------

def map_view() -> None:
    b, sid, lr = shared.load(), shared.sector_id(), shared.learner()
    t, path = b.t, b.paths[sid]

    bar = st.columns([5, 4], vertical_alignment="center")
    with bar[0]:
        ui.brand(t.t("app.title"))
    bar[1].html(ui.stats(lr.xp, lr.hints, lr.streak_days, t))

    top = st.columns([3, 2], gap="medium")
    with top[0].container(key="card_rank"):
        nxt = game.RANKS[min(lr.bosses_passed + 1, len(game.RANKS) - 1)]
        sub = t.t("game.top_rank") if lr.rank == game.RANKS[-1] else t.t("game.next_rank", rank=t.t(f"ranks.{nxt}"))
        st.html(ui.rank_card(t.t("game.rank_label"), t.t(f"ranks.{lr.rank}"), sub, len(path.stages), lr.bosses_passed))
        st.html(ui.badges([(t.t(f"badges.{bid}.name"), t.t(f"badges.{bid}.text"), bid in lr.badges)
                           for bid in game.BADGES]))
    with top[1].container(key="card_next"):
        up = path.next_up(lr)
        if up is None:
            st.html(ui.feedback("good", t.t("game.stage_done"), t.t("game.path_done")))
        elif up[0] == "step":
            step = path.step(up[1])
            stage_no = path.stages.index(path.stage_of(step.id)) + 1
            st.html(ui.crumb_title(t.t("game.stage", n=stage_no), lesson(step, t).get("title", step.id))
                    + ui.lead(lesson(step, t).get("intro", "")[:160].rsplit(" ", 1)[0] + "…"))
            if st.button(t.t("game.continue") if lr.xp else t.t("game.start"), type="primary",
                         icon=":material/play_arrow:", key="continue"):
                start_step(step.id)
                _rerun()
        else:
            stage = next(s for s in path.stages if s.id == up[1])
            st.html(ui.crumb_title(t.t("game.boss_ready"), t.t(f"bosses.{stage.id}.title"))
                    + ui.lead(t.t(f"bosses.{stage.id}.intro")))
            if st.button(t.t("game.start"), type="primary", icon=":material/shield:", key="continue"):
                start_boss(stage.id)
                _rerun()

    st.write("")
    for i, stage in enumerate(path.stages, 1):
        unlocked = path.stage_unlocked(lr, stage)
        with st.container(key=f"card_stage_{stage.id}"):
            status = (t.t("game.stage_done") if lr.boss(stage.id).passed else
                      "" if unlocked else t.t("game.locked"))
            st.html(ui.stage_head(f"{t.t('game.stage', n=i)} · {t.t(f'ranks.{stage.rank}')}"
                                  + (f" · {status}" if status else ""),
                                  t.t(f"stages.{stage.id}.title"), t.t(f"stages.{stage.id}.subtitle")))
            cols = st.columns(len(stage.steps) + 1)
            for j, step in enumerate(stage.steps):
                rec = lr.step(step.id)
                with cols[j]:
                    if rec.completed:
                        kind, label, icon = "done", "", ":material/check:"
                    elif path.step_unlocked(lr, step):
                        kind, label, icon = "open", str(j + 1), None
                    else:
                        kind, label, icon = "lock", "", ":material/lock:"
                    if st.button(label, key=f"node_{kind}_{step.id}", icon=icon, disabled=kind == "lock",
                                 help=lesson(step, t).get("title")):
                        start_step(step.id)
                        _rerun()
                    st.html(ui.node_label(lesson(step, t).get("title", step.id), rec.stars if rec.completed else None))
            with cols[-1]:
                boss_done, boss_open = lr.boss(stage.id).passed, path.boss_unlocked(lr, stage)
                if st.button("", key=f"node_{'bossdone' if boss_done else 'boss'}_{stage.id}",
                             icon=":material/emoji_events:" if boss_done else ":material/shield:",
                             disabled=not boss_open and not boss_done,
                             help=t.t("game.boss_locked") if not boss_open else None):
                    start_boss(stage.id)
                    _rerun()
                st.html(ui.node_label(f"{t.t('game.boss')}: {t.t(f'bosses.{stage.id}.title')}", None))
        st.write("")


# ---------------------------------------------------------------------------
# Level player
# ---------------------------------------------------------------------------

def reexplain(style: str, concepts: tuple[str, ...], chart_id: str | None, company: str) -> None:
    """Explain the same idea in a different way: plain words, analogy, another company, or its foundation."""
    b, sid = shared.load(), shared.sector_id()
    t, ex = b.t, b.explainers[sid]
    c = ex.concepts.get(concepts[0])
    title = t.t(f"game.style_{style}")
    if style == "other_company" and chart_id:
        other = next(r.ticker for r in b.sectors[sid].companies() if r.ticker != company)
        for r in b.sectors[sid].companies():
            e = ex.explain(shared.company_data(sid, r.ticker), chart_id)
            if r.ticker != company and e.available:
                other = r.ticker
                break
        e = ex.explain(shared.company_data(sid, other), chart_id)
        st.html(ui.feedback("info", t.t("game.explained_differently"), title))
        cols = st.columns([7, 5], gap="large")
        cols[0].altair_chart(e.figure, width="stretch", theme=None)
        cols[1].html(ui.observations(t.t("app.this_company", company=e.observations and
                                         shared.company_data(sid, other).ref.name), e.observations))
        return
    if style == "plain" and chart_id:
        # A misread chart needs the chart explained, not the definition repeated.
        g = ex.explain(shared.company_data(sid, company), chart_id).guide
        st.html(ui.feedback("info", f"{t.t('game.explained_differently')}: {title.lower()}",
                            f"{g.axes} {g.look_first}"))
        return
    if style == "prerequisite" and c and c.prerequisites:
        text = " ".join(f"{ex.concepts[p].name}: {ex.concepts[p].plain}" for p in c.prerequisites if p in ex.concepts)
    elif style == "analogy" and c and c.analogy:
        text = c.analogy
    else:
        text = f"{c.name}: {c.plain}" if c else ""
    st.html(ui.feedback("info", f"{t.t('game.explained_differently')}: {title.lower()}", text))


def step_player(a: dict) -> None:
    b, sid, lr = shared.load(), shared.sector_id(), shared.learner()
    t, path, ex, sector = b.t, b.paths[sid], b.explainers[sid], b.sectors[sid]
    step = path.step(a["id"])
    stage = path.stage_of(step.id)
    text = lesson(step, t)

    if st.button(t.t("game.back_to_map"), icon=":material/arrow_back:", key="back", type="tertiary"):
        back_to_map()
        _rerun()
    st.html(ui.crumb_title(f"{t.t('game.stage', n=path.stages.index(stage) + 1)} · "
                           f"{t.t('game.level', n=stage.steps.index(step) + 1)}", text.get("title", step.id))
            + ui.phases([t.t(p) for p in PHASES], a["phase"]))

    company = a["company"]
    if step.capstone and a["phase"] == 0:
        companies = {r.ticker: r for r in sector.companies()}
        company = st.selectbox(t.t("game.pick_company"), list(companies), index=list(companies).index(company),
                               format_func=lambda tk: companies[tk].name, key="capstone_company")
        a["company"] = company
    data = shared.company_data(sid, company)
    e = ex.explain(data, step.chart_id) if step.chart_id else None

    # -- 0. Look: ask before telling ----------------------------------------
    if a["phase"] == 0:
        with st.container(key="card_look"):
            st.html(ui.lead(text.get("intro", "")))
            if path.skippable(lr, step):
                st.html(ui.feedback("good", t.t("game.skip_mastered"), ""))
                if st.button(t.t("game.skip_mastered"), icon=":material/fast_forward:", key="skip_level"):
                    lr.skip_step(step.id)
                    back_to_map()
                    _rerun()
            cols = st.columns([7, 5], gap="large") if e else [st.container(), st.container()]
            if e:
                cols[0].altair_chart(e.figure, width="stretch", theme=None)
            else:
                with cols[0]:
                    ui.company_header(data.ref, data.headline(sector.headline_metrics()), ex.fmt)
            with cols[1]:
                st.html(ui.prompt(text.get("look_prompt", "")))
                note = st.text_area(t.t("game.your_turn"), key=f"obs_{step.id}", height=140,
                                    placeholder=t.t("game.observation_placeholder"), label_visibility="collapsed")
                go = st.columns(2)
                if go[0].button(t.t("game.show_me"), type="primary", key="show_me", width="stretch"):
                    a["obs_xp"] = lr.write_observation(step.id, note or "")
                    a["phase"] = 1
                    _rerun()
                if go[1].button(t.t("game.skip_observation"), key="skip_obs", width="stretch"):
                    a["phase"] = 1
                    _rerun()
        return

    # -- 1. Learn ---------------------------------------------------------------
    if a["phase"] == 1:
        new_terms = [ex.concepts[c] for c in step.concepts if c in ex.concepts and lr.is_new(c)]
        if not a["seen"]:
            lr.see(step.concepts)
            a["seen"], a["new_terms"] = True, [c.id for c in new_terms]
        with st.container(key="card_learn"):
            if e:
                cols = st.columns([7, 5], gap="large")
                cols[0].altair_chart(e.figure, width="stretch", theme=None)
                mine = lr.step(step.id).observation
                cols[1].html(ui.look_first(t.t("app.look_first"), e.guide.look_first)
                             + (ui.feedback("info", t.t("game.your_turn"), mine) if mine else "")
                             + ui.observations(t.t("app.this_company", company=data.ref.name), e.observations))
                st.html(ui.sector_notes(t.t("app.in_sector", sector=sector.name), e.sector_notes))
            else:
                st.html(ui.lead(text.get("intro", "")))
            for cid in a.get("new_terms", []):
                c = ex.concepts[cid]
                st.html(f'<div class="rn-eyebrow">{t.t("game.new_term")}</div>' + ui.term(c.name, c.plain, c.analogy))
            if text.get("takeaway"):
                st.html(ui.takeaway(t.t("game.takeaway"), text["takeaway"]))
            if st.button(t.t("game.check"), type="primary", icon=":material/quiz:", key="to_check"):
                a["phase"] = 2
                _rerun()
        return

    # -- 2. Check ---------------------------------------------------------------
    if a["phase"] == 2:
        qs = shared.step_questions(sid, step.id, company)
        q = qs[a["q"]]
        with st.container(key="card_check"):
            st.html(f'<div class="rn-eyebrow">{t.t("game.question_n", n=a["q"] + 1, total=len(qs))}</div>')
            qe = ex.explain(shared.company_data(sid, q.ticker), q.chart_id) if q.chart_id else None
            cols = st.columns([7, 5], gap="large") if qe else [None, st.container()]
            if qe:
                cols[0].altair_chart(qe.figure, width="stretch", theme=None)
            with cols[1]:
                st.html(ui.prompt(q.prompt))
                visible = [i for i in range(len(q.options)) if i not in a["hidden"]]
                choice = st.radio(q.prompt, visible, format_func=lambda i: q.options[i], index=None,
                                  key=f"ans_{step.id}_{a['q']}_{a['tries']}", label_visibility="collapsed",
                                  disabled=a["answered"] is not None)
                if a["answered"] is None:
                    row = st.columns([2, 1.4, 1.6])
                    if row[0].button(t.t("game.submit"), type="primary", disabled=choice is None, key="submit",
                                     width="stretch"):
                        correct = choice == q.answer
                        out = lr.answer(q.concepts, correct, q.variant, first_try=a["tries"] == 0)
                        a["answered"], a["style"] = correct, out.next_style
                        a["all_first"] &= correct and a["tries"] == 0
                        a["mastered"] += out.newly_mastered
                        a["badges"] += out.new_badges
                        _rerun()
                    if len(visible) > 2 and row[1].button(t.t("game.use_hint"), icon=":material/lightbulb:",
                                                          key="hint", width="stretch", disabled=lr.hints == 0):
                        if lr.use_hint():
                            a["hidden"].append(next(i for i in visible if i != q.answer))
                        _rerun()
                    if row[2].button(t.t("game.dont_get_it"), icon=":material/help:", key="lost", width="stretch"):
                        a["style"] = lr.struggle(q.concepts)
                        _rerun()
                    if lr.hints == 0 and len(visible) > 2:
                        st.caption(t.t("game.no_hints"))
                elif a["answered"]:
                    st.html(ui.feedback("good", t.t("game.correct"), q.why))
                else:
                    reveal = a["tries"] >= 1
                    st.html(ui.feedback("warn", t.t("game.not_quite"), q.why if reveal else ""))
            if a["style"] and not a["answered"]:
                reexplain(a["style"], q.concepts, q.chart_id, company)
            nav = st.columns([2, 5])
            if a["answered"] or (a["answered"] is False and a["tries"] >= 1):
                last = a["q"] + 1 >= len(qs)
                if nav[0].button(t.t("game.finish_level") if last else t.t("game.next_question"), type="primary",
                                 key="next_q", width="stretch"):
                    if last:
                        a["phase"] = 3
                    else:
                        a.update(q=a["q"] + 1, tries=0, answered=None, hidden=[], style=None)
                    _rerun()
            elif a["answered"] is False:
                if nav[0].button(t.t("game.try_again"), type="primary", key="retry", width="stretch"):
                    a.update(tries=a["tries"] + 1, answered=None)
                    _rerun()
        return

    # -- 3. Done ----------------------------------------------------------------
    if "stars" not in a:
        a["stars"] = lr.complete_step(step.id, a["all_first"])
    rec = lr.step(step.id)
    chips = [t.t("game.xp_earned", xp=lr.xp - a["xp0"])]
    chips += [t.t("game.mastered", concepts=ex.concepts[c].name) for c in a["mastered"] if c in ex.concepts]
    chips += [t.t("game.new_badge", badge=t.t(f"badges.{bid}.name")) for bid in a["badges"]]
    with st.container(key="card_done"):
        st.html(ui.celebrate("trophy", t.t("game.level_complete"), t.t("game.stars_earned", stars=a["stars"]), chips)
                + ui.stars(a["stars"], big=True))
        reasons = [("check", t.t("game.star_finish"), True), ("check", t.t("game.star_first_try"), a["all_first"]),
                   ("check", t.t("game.star_own_words"), len(rec.observation.split()) >= game.MIN_OBSERVATION_WORDS)]
        st.html('<div class="rn-guide" style="max-width:420px;margin:1rem auto 0">' + "".join(
            f'<div>{ui.icon("check" if ok else "x", 18)}<span>{text_}</span></div>' for _, text_, ok in reasons)
                + "</div>")
        if text.get("takeaway"):
            st.html(ui.takeaway(t.t("game.takeaway"), text["takeaway"]))
        row = st.columns([1, 2, 2, 1])
        up = path.next_up(lr)
        if up and row[1].button(t.t("game.continue"), type="primary", key="next_level", width="stretch",
                                icon=":material/arrow_forward:"):
            start_step(up[1]) if up[0] == "step" else start_boss(up[1])
            _rerun()
        if row[2].button(t.t("game.back_to_map"), key="map", width="stretch"):
            back_to_map()
            _rerun()


# ---------------------------------------------------------------------------
# Boss
# ---------------------------------------------------------------------------

def boss_player(a: dict) -> None:
    b, sid, lr = shared.load(), shared.sector_id(), shared.learner()
    t, path, ex = b.t, b.paths[sid], b.explainers[sid]
    stage = next(s for s in path.stages if s.id == a["stage"])
    ticker, qs = shared.boss_questions(sid, stage.id, a["attempt"])
    mystery = mask(shared.company_data(sid, ticker), t.t("game.mystery_name"))

    if st.button(t.t("game.back_to_map"), icon=":material/arrow_back:", key="back", type="tertiary"):
        back_to_map()
        _rerun()
    st.html(ui.crumb_title(f"{t.t('game.stage', n=path.stages.index(stage) + 1)} · {t.t('game.boss')}",
                           t.t(f"bosses.{stage.id}.title")))

    if a["phase"] == "intro":
        with st.container(key="card_boss_intro"):
            st.html(ui.celebrate("shield", t.t(f"bosses.{stage.id}.title"), t.t(f"bosses.{stage.id}.intro"),
                                 [t.t("game.boss_score", score=game.BOSS_PASS_MARK, total=game.BOSS_QUESTIONS,
                                      needed=game.BOSS_PASS_MARK).split("(")[-1].rstrip(").")]))
            row = st.columns([2, 2, 2])
            if row[1].button(t.t("game.start"), type="primary", key="boss_go", width="stretch",
                             icon=":material/play_arrow:"):
                a["phase"] = "q"
                _rerun()
        return

    if a["phase"] == "q":
        q = qs[a["q"]]
        with st.container(key="card_boss_q"):
            st.html(f'<div class="rn-eyebrow">{t.t("game.question_n", n=a["q"] + 1, total=len(qs))}</div>')
            e = ex.explain(mystery, q.chart_id)
            cols = st.columns([7, 5], gap="large")
            cols[0].altair_chart(e.figure, width="stretch", theme=None)
            with cols[1]:
                st.html(ui.prompt(q.prompt))
                choice = st.radio(q.prompt, range(len(q.options)), format_func=lambda i: q.options[i], index=None,
                                  key=f"boss_{stage.id}_{a['attempt']}_{a['q']}", label_visibility="collapsed",
                                  disabled=a["answered"] is not None)
                if a["answered"] is None:
                    if st.button(t.t("game.submit"), type="primary", disabled=choice is None, key="boss_submit"):
                        correct = choice == q.answer
                        lr.answer(q.concepts, correct, q.variant, first_try=True)
                        a["answered"] = correct
                        a["score"] += int(correct)
                        _rerun()
                else:
                    st.html(ui.feedback("good" if a["answered"] else "warn",
                                        t.t("game.correct") if a["answered"] else t.t("game.not_quite"), q.why))
                    last = a["q"] + 1 >= len(qs)
                    if st.button(t.t("game.finish_level") if last else t.t("game.next_question"), type="primary",
                                 key="boss_next"):
                        if last:
                            a["phase"] = "result"
                        else:
                            a.update(q=a["q"] + 1, answered=None)
                        _rerun()
        return

    if a["result"] is None:
        a["result"] = lr.finish_boss(stage.id, a["score"])
    name = b.sectors[sid].company_data(ticker).ref.name if False else shared.company_data(sid, ticker).ref.name
    with st.container(key="card_boss_result"):
        chips = [t.t("game.boss_score", score=a["score"], total=len(qs), needed=game.BOSS_PASS_MARK),
                 t.t("game.reveal", name=name)]
        if a["result"]:
            promoted = lr.rank != a["rank0"]
            chips.insert(0, t.t("game.xp_earned", xp=lr.xp - a["xp0"]))
            title = t.t("game.promoted", rank=t.t(f"ranks.{lr.rank}")) if promoted else t.t("game.boss_passed")
            st.html(ui.celebrate("trophy" if promoted else "check", title, t.t("game.boss_passed"), chips))
        else:
            st.html(ui.celebrate("shield", t.t("game.boss_failed"), t.t("game.boss_retry"), chips))
        row = st.columns([1, 2, 2, 1])
        if not a["result"] and row[1].button(t.t("game.try_again"), type="primary", key="boss_again", width="stretch"):
            start_boss(stage.id)
            _rerun()
        up = path.next_up(lr)
        if a["result"] and up and row[1].button(t.t("game.continue"), type="primary", key="boss_continue",
                                                width="stretch", icon=":material/arrow_forward:"):
            start_step(up[1]) if up[0] == "step" else start_boss(up[1])
            _rerun()
        if row[2].button(t.t("game.back_to_map"), key="boss_map", width="stretch"):
            back_to_map()
            _rerun()


def render() -> None:
    a = st.session_state.get("activity")
    if a is None:
        map_view()
    elif a["type"] == "step":
        step_player(a)
    else:
        boss_player(a)
