"""Progress: what the learner has mastered, and what carries over to other industries."""

import shared
import streamlit as st
import ui

from valuation_tutor.core import game
from valuation_tutor.core.concepts import CORE_CONCEPTS


def chip(name: str, state: str, t) -> str:
    cls = {"mastered": "", "learning": " learning", "new": " off"}[state]
    label = t.t(f"progress.state_{state}")
    return f'<span class="rn-badge{cls}" title="{label}">{ui.icon("check" if state == "mastered" else "dot", 14)}{name}</span>'


def render() -> None:
    b, lr = shared.load(), shared.learner()
    t = b.t
    bar = st.columns([5, 4], vertical_alignment="center")
    with bar[0]:
        ui.brand(t.t("app.title"))
    bar[1].html(ui.stats(lr.xp, lr.hints, lr.streak_days, t))
    st.html(ui.crumb_title(t.t("progress.eyebrow"), t.t("progress.title")) + ui.lead(t.t("progress.intro")))
    if not shared.account():
        st.html(ui.feedback("info", t.t("progress.guest_title"),
                            t.t("progress.guest_text") if shared.auth_configured() else t.t("progress.local_text")))

    def state(cid: str) -> str:
        c = lr.concepts.get(cid)
        return "mastered" if c and c.mastered else "learning" if c and c.attempts else "new"

    ex = next(iter(b.explainers.values()))
    with st.container(key="card_universal"):
        st.html(ui.prompt(t.t("progress.universal")) + f'<p class="rn-section-intro">{t.t("progress.universal_note")}</p>'
                + '<div class="rn-badges">' + "".join(chip(ex.concepts[c].name, state(c), t) for c in CORE_CONCEPTS)
                + "</div>")
    st.write("")
    for sid, sector in b.sectors.items():
        path, sex = b.paths[sid], b.explainers[sid]
        with st.container(key=f"card_sector_{sid}"):
            stars = sum(path.record(lr, s).stars for s in path.steps)
            st.html(ui.crumb_title(sector.name, t.t(f"ranks.{path.rank(lr)}"))
                    + ui.lead(t.t("progress.sector_summary", stars=stars, max=3 * len(path.steps),
                                  bosses=path.bosses_passed(lr), stages=len(path.stages))))
            own = [c for c in sector.concepts()]
            if own:
                st.html(f'<div class="rn-eyebrow">{t.t("progress.sector_ideas", sector=sector.name)}</div>'
                        + '<div class="rn-badges">' + "".join(chip(c.name, state(c.id), t) for c in own) + "</div>")
            rows = []
            for i, stage in enumerate(path.stages, 1):
                cells = "".join(
                    f'<div style="display:flex;justify-content:space-between;gap:1rem;padding:.25rem 0">'
                    f'<span>{(s.lesson or t.get("lessons." + s.id) or {}).get("title", s.id)}</span>'
                    f'{ui.stars(path.record(lr, s).stars)}</div>' for s in stage.steps)
                boss = "✓" if path.boss_record(lr, stage).passed else ""
                rows.append(f'<div style="margin-top:.8rem"><div class="rn-eyebrow">{t.t("game.stage", n=i)} · '
                            f'{t.t(f"stages.{stage.id}.title")} {boss}</div>{cells}</div>')
            st.html("".join(rows))
        st.write("")
    with st.container(key="card_badges"):
        st.html(ui.prompt(t.t("game.badges")) + ui.badges(
            [(t.t(f"badges.{bid}.name"), t.t(f"badges.{bid}.text"), bid in lr.badges) for bid in game.BADGES]))
