"""Design system for the app: tokens, icons, global CSS and HTML components.

Streamlit's theme (.streamlit/config.toml) sets fonts, colours and radii for
built-in widgets; this module adds the pieces Streamlit doesn't have (company
header, key-number tiles, observation list, hints) as small HTML blocks.

Rules: no emoji as icons; status colour always comes with an icon (never colour
alone); one accent colour (the same blue as the charts); text is escaped.
"""

from __future__ import annotations

from html import escape
from urllib.parse import quote

import streamlit as st

from valuation_tutor.core.charts import Observation
from valuation_tutor.core.fmt import Formatter
from valuation_tutor.core.sector import CompanyRef, Fact

TOKENS = {
    "ink": "#1d1d1b", "ink2": "#52514e", "muted": "#7a7972", "line": "#e4e2da",
    "card": "#ffffff", "page": "#f6f5f1",
    "accent": "#2a78d6", "accent_ink": "#1f5fae", "accent_soft": "#eaf2fc",
    "good": "#0ca30c", "good_ink": "#006300", "good_soft": "#e7f5e7",
    "warn": "#c27a00", "warn_ink": "#7a4d00", "warn_soft": "#fdf1d8",
    "neutral_soft": "#eef0f3",
}

# 24x24 line icons, drawn for this app (stroke = currentColor).
_PATHS = {
    "check": '<path d="M20 6 9 17l-5-5"/>',
    "alert": '<path d="M12 4 2.5 20h19L12 4z"/><path d="M12 10v4"/><path d="M12 17.2v.1"/>',
    "dot": '<circle cx="12" cy="12" r="3.2" fill="currentColor" stroke="none"/>',
    "eye": '<path d="M2 12s3.6-7 10-7 10 7 10 7-3.6 7-10 7S2 12 2 12z"/><circle cx="12" cy="12" r="3"/>',
    "book": '<path d="M3 5.5C5.5 4 9 4 12 6c3-2 6.5-2 9-.5V19c-2.5-1.5-6-1.5-9 .5-3-2-6.5-2-9-.5z"/>'
            '<path d="M12 6v13.5"/>',
    "info": '<circle cx="12" cy="12" r="9"/><path d="M12 11v5"/><path d="M12 7.8v.1"/>',
    "spark": '<path d="M12 3v4M12 17v4M3 12h4M17 12h4M6 6l2.5 2.5M15.5 15.5 18 18M6 18l2.5-2.5M15.5 8.5 18 6"/>',
    "star": '<path d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "star_fill": '<path fill="black" d="m12 3 2.7 5.6 6.1.9-4.4 4.3 1 6.1L12 17l-5.4 2.9 1-6.1-4.4-4.3 6.1-.9z"/>',
    "bolt": '<path d="M13 2 4 14h7l-1 8 9-12h-7z"/>',
    "flame": '<path d="M12 22c4 0 7-2.7 7-7 0-4-3-6.5-4-10-2 2-3 4-3 6-1-1-2-2.5-2-4-2 2-5 5-5 8 0 4.3 3 7 7 7z"/>',
    "bulb": '<path d="M9 18h6M10 21h4M12 3a6 6 0 0 0-4 10.5c.8.8 1 1.5 1 2.5h6c0-1 .2-1.7 1-2.5A6 6 0 0 0 12 3z"/>',
    "shield": '<path d="M12 3 4 6v6c0 5 3.5 8 8 9 4.5-1 8-4 8-9V6z"/>',
    "trophy": '<path d="M8 4h8v5a4 4 0 0 1-8 0zM8 6H4v1a4 4 0 0 0 4 4M16 6h4v1a4 4 0 0 1-4 4M12 13v4M8 21h8M9 17h6v4H9z"/>',
    "medal": '<circle cx="12" cy="15" r="5"/><path d="M8.5 11 6 3h4l2 5 2-5h4l-2.5 8"/>',
    "lock": '<rect x="5" y="11" width="14" height="10" rx="2"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/>',
    "x": '<path d="M18 6 6 18M6 6l12 12"/>',
}


def _mask(path: str) -> str:
    svg = (f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='black' "
           f"stroke-width='2' stroke-linecap='round' stroke-linejoin='round'>{path}</svg>")
    # Fully percent-encoded: the HTML sanitizer drops a <style> block containing "<svg" text.
    return f'url("data:image/svg+xml;utf8,{quote(svg)}")'


# Icons are CSS masks (st.html strips inline SVG); they take the text colour.
ICON_CSS = "".join(f".rn-i-{name} {{ -webkit-mask-image: {_mask(p)}; mask-image: {_mask(p)}; }}\n"
                   for name, p in _PATHS.items())


def icon(name: str, size: int = 16) -> str:
    return f'<span class="rn-i rn-i-{name}" style="width:{size}px;height:{size}px" aria-hidden="true"></span>'


TONE = {  # tone -> (icon, icon colour, background, label for screen readers)
    "good": ("check", TOKENS["good"], TOKENS["good_soft"], "Good sign"),
    "warning": ("alert", TOKENS["warn"], TOKENS["warn_soft"], "Worth a closer look"),
    "neutral": ("dot", TOKENS["accent"], TOKENS["accent_soft"], "Observation"),
}

CSS = f"""
<style>
/* Layout: a centred column, no sidebar, quiet header */
[data-testid="stSidebar"], [data-testid="stSidebarCollapsedControl"] {{ display: none; }}
[data-testid="stHeader"] {{ background: transparent; }}
[data-testid="stMainBlockContainer"] {{ max-width: 1180px; padding-top: 4.25rem; padding-bottom: 4rem; }}  /* clear the fixed top nav */
.rn-i {{ display: inline-block; vertical-align: -3px; flex: none; background-color: currentColor;
  -webkit-mask-repeat: no-repeat; mask-repeat: no-repeat; -webkit-mask-size: contain; mask-size: contain; }}

/* App bar */
.rn-brand {{ display: flex; align-items: center; gap: .6rem; height: 2.5rem; }}
.rn-brand-mark {{ width: 2rem; height: 2rem; border-radius: .6rem; background: {TOKENS['accent']};
  display: grid; place-items: center; color: white; }}
.rn-brand-name {{ font-family: 'Plus Jakarta Sans', sans-serif; font-weight: 800; font-size: 1.1rem;
  color: {TOKENS['ink']}; letter-spacing: -.01em; }}

/* Cards: any st.container whose key starts with "card" */
[class*="st-key-card"] {{ background: {TOKENS['card']}; border: 1px solid {TOKENS['line']};
  border-radius: 1.25rem; padding: 1.4rem 1.6rem 1.2rem;
  box-shadow: 0 1px 2px rgba(29,29,27,.04), 0 12px 32px -20px rgba(29,29,27,.18); }}

/* Company header */
.rn-hero {{ display: flex; align-items: baseline; gap: .75rem; flex-wrap: wrap; margin: .2rem 0 1rem; }}
.rn-hero h1 {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 2.4rem; font-weight: 800;
  letter-spacing: -.02em; margin: 0; padding: 0; color: {TOKENS['ink']}; line-height: 1.1; }}
.rn-chip {{ display: inline-flex; align-items: center; gap: .3rem; padding: .2rem .65rem; border-radius: 999px;
  font-size: .8rem; font-weight: 600; background: {TOKENS['neutral_soft']}; color: {TOKENS['ink2']}; }}
.rn-chip.accent {{ background: {TOKENS['accent_soft']}; color: {TOKENS['accent_ink']}; }}
.rn-kpis {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(170px, 1fr)); gap: .75rem; }}
.rn-kpi {{ background: {TOKENS['card']}; border: 1px solid {TOKENS['line']}; border-radius: 1rem; padding: .9rem 1.1rem; }}
.rn-kpi-label {{ font-size: .82rem; color: {TOKENS['ink2']}; font-weight: 500; }}
.rn-kpi-value {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.65rem; font-weight: 800;
  color: {TOKENS['ink']}; letter-spacing: -.01em; margin-top: .15rem; }}
.rn-kpi-period {{ font-size: .75rem; color: {TOKENS['muted']}; }}

/* Card internals */
.rn-eyebrow {{ font-size: .78rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase;
  color: {TOKENS['muted']}; margin: .1rem 0 .55rem; }}
.rn-look {{ display: flex; gap: .6rem; background: {TOKENS['accent_soft']}; color: {TOKENS['accent_ink']};
  border-radius: .9rem; padding: .75rem .9rem; font-size: .92rem; line-height: 1.45; margin-bottom: 1rem; }}
.rn-look b {{ display: block; font-size: .78rem; text-transform: uppercase; letter-spacing: .04em; }}
.rn-obs {{ list-style: none; padding: 0; margin: 0 0 .9rem; display: grid; gap: .65rem; }}
.rn-obs li {{ display: flex; gap: .65rem; align-items: flex-start; font-size: .95rem; line-height: 1.5;
  color: {TOKENS['ink']}; margin: 0; }}
.rn-tone {{ width: 1.6rem; height: 1.6rem; border-radius: 999px; display: grid; place-items: center;
  flex: none; margin-top: .05rem; }}
.rn-note {{ display: flex; gap: .7rem; background: {TOKENS['page']}; border-radius: .9rem; padding: .8rem 1rem;
  font-size: .88rem; color: {TOKENS['ink2']}; line-height: 1.5; margin-top: .4rem; }}
.rn-note .rn-i {{ color: {TOKENS['ink2']}; margin-top: .15rem; }}
.rn-note b {{ color: {TOKENS['ink']}; }}
.rn-note p {{ margin: 0 0 .3rem; }}
.rn-guide {{ display: grid; gap: .9rem; font-size: .92rem; line-height: 1.5; color: {TOKENS['ink']}; }}
.rn-guide div {{ display: flex; gap: .6rem; }}
.rn-guide b {{ display: block; font-size: .8rem; color: {TOKENS['ink2']}; }}
.rn-term {{ background: {TOKENS['page']}; border-radius: .9rem; padding: .8rem 1rem; font-size: .92rem;
  line-height: 1.5; margin-top: .4rem; }}
.rn-term i {{ color: {TOKENS['ink2']}; }}
.rn-footer {{ color: {TOKENS['muted']}; font-size: .8rem; text-align: center; margin-top: 2.5rem; }}
.rn-section-intro {{ color: {TOKENS['ink2']}; font-size: 1rem; margin: -.2rem 0 1rem; }}

/* --- Game ------------------------------------------------------------ */
.rn-rank {{ display: flex; align-items: center; gap: 1.1rem; }}
.rn-rank-badge {{ width: 3.4rem; height: 3.4rem; border-radius: 1rem; display: grid; place-items: center;
  background: linear-gradient(135deg, {TOKENS['accent']} 0%, #5b5bd6 100%); color: white; flex: none; }}
.rn-rank small {{ display: block; font-size: .78rem; color: {TOKENS['muted']}; font-weight: 600;
  text-transform: uppercase; letter-spacing: .04em; }}
.rn-rank strong {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.5rem; font-weight: 800; color: {TOKENS['ink']}; }}
.rn-rank p {{ margin: .1rem 0 0; color: {TOKENS['ink2']}; font-size: .88rem; }}
.rn-ladder {{ display: flex; gap: .3rem; margin-top: .6rem; }}
.rn-ladder span {{ flex: 1; height: .45rem; border-radius: 999px; background: {TOKENS['line']}; }}
.rn-ladder span.on {{ background: {TOKENS['accent']}; }}
.rn-stats {{ display: flex; gap: .5rem; flex-wrap: wrap; justify-content: flex-end; }}
.rn-stat {{ display: inline-flex; align-items: center; gap: .4rem; padding: .45rem .8rem; border-radius: 999px;
  background: {TOKENS['card']}; border: 1px solid {TOKENS['line']}; font-weight: 700; font-size: .9rem; color: {TOKENS['ink']}; }}
.rn-stat .rn-i {{ color: {TOKENS['accent']}; }}
.rn-stat.xp .rn-i {{ color: #c27a00; }} .rn-stat.streak .rn-i {{ color: #e8590c; }}
.rn-badges {{ display: flex; gap: .5rem; flex-wrap: wrap; }}
.rn-badge {{ display: inline-flex; align-items: center; gap: .45rem; padding: .35rem .75rem .35rem .4rem;
  border-radius: 999px; background: #fff7e0; color: #7a4d00; font-size: .85rem; font-weight: 600; }}
.rn-badge .rn-i {{ background-color: #c27a00; }}
.rn-badge.off {{ background: {TOKENS['neutral_soft']}; color: {TOKENS['muted']}; }}
.rn-badge.off .rn-i {{ background-color: {TOKENS['muted']}; }}
.rn-stage-head {{ display: flex; align-items: center; gap: .8rem; }}
.rn-stage-num {{ font-size: .78rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: {TOKENS['accent_ink']}; }}
.rn-stage-head h3 {{ margin: 0; padding: 0; font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.3rem; font-weight: 800; }}
.rn-stage-head p {{ margin: .1rem 0 0; color: {TOKENS['ink2']}; font-size: .92rem; }}
.rn-node-label {{ text-align: center; font-size: .82rem; color: {TOKENS['ink2']}; line-height: 1.3; margin-top: .15rem;
  min-height: 2.1em; padding: 0 .3rem; }}
.rn-stars {{ display: flex; justify-content: center; gap: .1rem; color: #e0a100; }}
.rn-stars .rn-i.empty {{ background-color: {TOKENS['line']}; }}
.rn-stars.big {{ gap: .4rem; }}
[class*="st-key-node"] {{ width: 100% !important; display: flex; justify-content: center; }}
[class*="st-key-node"] [data-testid="stButton"] {{ display: flex; justify-content: center; width: 100%; }}
[class*="st-key-node"] button {{ width: 4rem !important; height: 4rem; min-height: 4rem; border-radius: 999px !important;
  margin: 0 auto; display: flex; font-weight: 800; font-size: 1.1rem; padding: 0; }}
[class*="st-key-node_done"] button {{ background: {TOKENS['good_soft']}; border-color: #9fd59f; color: {TOKENS['good_ink']}; }}
[class*="st-key-node_open"] button {{ background: {TOKENS['accent']}; border-color: {TOKENS['accent']}; color: white;
  box-shadow: 0 0 0 6px {TOKENS['accent_soft']}; }}
[class*="st-key-node_boss"] button {{ background: #2b2a52; border-color: #2b2a52; color: #ffd76a; }}
[class*="st-key-node_bossdone"] button {{ background: #fff3c4; border-color: #f1d27a; color: #7a4d00; }}
[class*="st-key-node"] button:disabled {{ background: {TOKENS['neutral_soft']}; color: {TOKENS['muted']}; border-color: {TOKENS['line']}; box-shadow: none; }}
.rn-phases {{ display: flex; gap: .4rem; align-items: center; margin: .2rem 0 1rem; flex-wrap: wrap; }}
.rn-phase {{ display: inline-flex; align-items: center; gap: .35rem; font-size: .82rem; font-weight: 600;
  padding: .25rem .7rem; border-radius: 999px; background: {TOKENS['neutral_soft']}; color: {TOKENS['muted']}; }}
.rn-phase.on {{ background: {TOKENS['accent']}; color: white; }}
.rn-phase.done {{ background: {TOKENS['good_soft']}; color: {TOKENS['good_ink']}; }}
.rn-lead {{ font-size: 1.05rem; line-height: 1.6; color: {TOKENS['ink']}; margin: 0 0 .8rem; }}
.rn-prompt {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.15rem; font-weight: 700; color: {TOKENS['ink']};
  margin: .2rem 0 .4rem; }}
.rn-feedback {{ display: flex; gap: .75rem; border-radius: 1rem; padding: .9rem 1.1rem; margin: .6rem 0; font-size: .95rem; line-height: 1.5; }}
.rn-feedback.good {{ background: {TOKENS['good_soft']}; color: {TOKENS['good_ink']}; }}
.rn-feedback.warn {{ background: {TOKENS['warn_soft']}; color: {TOKENS['warn_ink']}; }}
.rn-feedback.info {{ background: {TOKENS['accent_soft']}; color: {TOKENS['accent_ink']}; }}
.rn-feedback b {{ display: block; margin-bottom: .1rem; }}
.rn-feedback .rn-i {{ margin-top: .2rem; }}
.rn-celebrate {{ text-align: center; padding: 1rem 0 .4rem; }}
.rn-celebrate .rn-big {{ width: 4.5rem; height: 4.5rem; border-radius: 1.4rem; margin: 0 auto .8rem; display: grid;
  place-items: center; color: white; background: linear-gradient(135deg, {TOKENS['accent']} 0%, #5b5bd6 100%); }}
.rn-celebrate h2 {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 1.9rem; font-weight: 800; margin: 0; padding: 0; }}
.rn-celebrate p {{ color: {TOKENS['ink2']}; margin: .3rem 0 0; }}
.rn-gain {{ display: flex; justify-content: center; gap: .5rem; flex-wrap: wrap; margin-top: .9rem; }}
.rn-takeaway {{ display: flex; gap: .7rem; background: #fff7e0; color: #5c3b00; border-radius: 1rem; padding: .85rem 1.05rem;
  font-size: .95rem; line-height: 1.5; margin-top: .8rem; }}
.rn-takeaway .rn-i {{ background-color: #c27a00; margin-top: .15rem; }}
.rn-crumb {{ font-size: .82rem; font-weight: 700; letter-spacing: .04em; text-transform: uppercase; color: {TOKENS['accent_ink']}; }}
.rn-title {{ font-family: 'Plus Jakarta Sans', sans-serif; font-size: 2rem; font-weight: 800; letter-spacing: -.02em;
  margin: .1rem 0 .3rem; color: {TOKENS['ink']}; line-height: 1.15; }}

/* Tutor */
.rn-tutor {{ display: flex; gap: .8rem; margin: .4rem 0 .8rem; }}
.rn-tutor-avatar {{ width: 2.2rem; height: 2.2rem; border-radius: .8rem; flex: none; display: grid; place-items: center;
  color: white; background: linear-gradient(135deg, {TOKENS['accent']} 0%, #5b5bd6 100%); }}
.rn-tutor-body {{ flex: 1; background: {TOKENS['card']}; border: 1px solid {TOKENS['line']}; border-radius: .3rem 1rem 1rem 1rem;
  padding: .75rem 1rem; font-size: .96rem; line-height: 1.55; color: {TOKENS['ink']}; }}
.rn-tutor-body .who {{ font-size: .78rem; font-weight: 700; color: {TOKENS['accent_ink']}; text-transform: uppercase;
  letter-spacing: .04em; display: block; margin-bottom: .2rem; }}
.rn-tutor-body sup {{ font-size: .68rem; font-weight: 700; color: {TOKENS['accent_ink']}; background: {TOKENS['accent_soft']};
  border-radius: 999px; padding: 0 .3rem; margin-left: .1rem; cursor: help; }}
.rn-tutor-src {{ margin-top: .55rem; padding-top: .5rem; border-top: 1px solid {TOKENS['line']}; font-size: .78rem;
  color: {TOKENS['muted']}; display: grid; gap: .15rem; }}
.rn-me {{ display: flex; justify-content: flex-end; margin: .4rem 0; }}
.rn-me span {{ background: {TOKENS['accent_soft']}; color: {TOKENS['ink']}; border-radius: 1rem 1rem .3rem 1rem;
  padding: .55rem .9rem; font-size: .94rem; max-width: 80%; line-height: 1.5; }}

/* Card header buttons (popovers) as quiet pills */
[class*="st-key-card"] [data-testid="stPopover"] button {{ border-color: {TOKENS['line']}; font-size: .85rem;
  padding: .2rem .8rem; min-height: 2rem; }}
</style>
"""


def inject_css(direction: str = "ltr") -> None:
    rtl = ".stApp { direction: rtl; text-align: right; }" if direction == "rtl" else ""
    st.html(CSS + f"<style>{ICON_CSS}{rtl}</style>")


def brand(name: str) -> None:
    st.html(f'<div class="rn-brand"><div class="rn-brand-mark">{icon("spark", 18)}</div>'
            f'<span class="rn-brand-name">{escape(name)}</span></div>')


def company_header(ref: CompanyRef, headline: list[Fact], fmt: Formatter) -> None:
    tiles = "".join(
        f'<div class="rn-kpi" title="{escape(f.source)}"><div class="rn-kpi-label">{escape(f.label)}</div>'
        f'<div class="rn-kpi-value">{escape(fmt.fact(f))}</div>'
        f'<div class="rn-kpi-period">{escape(f.period)}</div></div>' for f in headline)
    st.html(f'<div class="rn-hero"><h1>{escape(ref.name)}</h1><span class="rn-chip">{escape(ref.ticker)}</span>'
            f'<span class="rn-chip accent">{escape(ref.profile_label)}</span></div>'
            f'<div class="rn-kpis">{tiles}</div>')


def look_first(label: str, text: str) -> str:
    return f'<div class="rn-look">{icon("eye", 18)}<div><b>{escape(label)}</b>{escape(text)}</div></div>'


def observations(heading: str, items: list[Observation]) -> str:
    rows = []
    for o in items:
        name, colour, bg, aria = TONE[o.tone]
        rows.append(f'<li><span class="rn-tone" style="background:{bg};color:{colour}" role="img" '
                    f'aria-label="{aria}">{icon(name, 14)}</span><span>{escape(o.text)}</span></li>')
    return f'<div class="rn-eyebrow">{escape(heading)}</div><ul class="rn-obs">{"".join(rows)}</ul>'


def sector_notes(heading: str, notes: tuple[str, ...]) -> str:
    if not notes:
        return ""
    body = "".join(f"<p>{escape(n)}</p>" for n in notes)
    return f'<div class="rn-note">{icon("info", 18)}<div><b>{escape(heading)}</b>{body}</div></div>'


def guide(rows: list[tuple[str, str, str]]) -> str:
    """rows: (icon name, label, text)."""
    return '<div class="rn-guide">' + "".join(
        f'<div>{icon(i, 18)}<span><b>{escape(label)}</b>{escape(text)}</span></div>' for i, label, text in rows
    ) + "</div>"


def term(name: str, plain: str, analogy: str) -> str:
    extra = f"<br><i>{escape(analogy)}</i>" if analogy else ""
    return f'<div class="rn-term"><b>{escape(name)}</b>: {escape(plain)}{extra}</div>'


def stats(xp: int, hints: int, streak: int, t) -> str:
    return (f'<div class="rn-stats"><span class="rn-stat xp">{icon("bolt", 16)}{escape(t.t("game.xp", xp=xp))}</span>'
            f'<span class="rn-stat">{icon("bulb", 16)}{escape(t.t("game.hints", n=hints))}</span>'
            f'<span class="rn-stat streak">{icon("flame", 16)}'
            f'{escape(t.t("game.streak", n=streak) if streak else t.t("game.no_streak"))}</span></div>')


def rank_card(label: str, rank: str, sub: str, steps: int, done: int) -> str:
    ladder = "".join(f'<span class="{"on" if i < done else ""}"></span>' for i in range(steps))
    return (f'<div class="rn-rank"><div class="rn-rank-badge">{icon("medal", 28)}</div><div style="flex:1">'
            f'<small>{escape(label)}</small><strong>{escape(rank)}</strong><p>{escape(sub)}</p>'
            f'<div class="rn-ladder">{ladder}</div></div></div>')


def badges(items: list[tuple[str, str, bool]]) -> str:
    """items: (name, description, earned)."""
    return '<div class="rn-badges">' + "".join(
        f'<span class="rn-badge{"" if on else " off"}" title="{escape(text)}">{icon("medal", 16)}{escape(name)}</span>'
        for name, text, on in items) + "</div>"


def stage_head(number: str, title: str, subtitle: str) -> str:
    return (f'<div class="rn-stage-head"><div><div class="rn-stage-num">{escape(number)}</div>'
            f'<h3>{escape(title)}</h3><p>{escape(subtitle)}</p></div></div>')


def stars(n: int, big: bool = False) -> str:
    size = 26 if big else 13
    return f'<div class="rn-stars{" big" if big else ""}">' + "".join(
        icon("star_fill", size) if i < n else icon("star_fill", size).replace('class="rn-i', 'class="rn-i empty')
        for i in range(3)) + "</div>"


def node_label(text: str, n_stars: int | None) -> str:
    return (stars(n_stars) if n_stars is not None else '<div class="rn-stars">&nbsp;</div>') + \
        f'<div class="rn-node-label">{escape(text)}</div>'


def phases(names: list[str], current: int) -> str:
    return '<div class="rn-phases">' + "".join(
        f'<span class="rn-phase {"on" if i == current else "done" if i < current else ""}">'
        f'{icon("check", 13) if i < current else ""}{escape(n)}</span>' for i, n in enumerate(names)) + "</div>"


def crumb_title(crumb: str, title: str) -> str:
    return f'<div class="rn-crumb">{escape(crumb)}</div><div class="rn-title">{escape(title)}</div>'


def lead(text: str) -> str:
    return f'<p class="rn-lead">{escape(text)}</p>'


def prompt(text: str) -> str:
    return f'<div class="rn-prompt">{escape(text)}</div>'


def feedback(kind: str, title: str, text: str) -> str:
    name = {"good": "check", "warn": "alert", "info": "bulb"}[kind]
    return (f'<div class="rn-feedback {kind}">{icon(name, 18)}<div><b>{escape(title)}</b>'
            f'{escape(text)}</div></div>')


def takeaway(label: str, text: str) -> str:
    return f'<div class="rn-takeaway">{icon("bulb", 18)}<div><b>{escape(label)}:</b> {escape(text)}</div></div>'


def celebrate(icon_name: str, title: str, sub: str, chips: list[str] = ()) -> str:
    gains = "".join(f'<span class="rn-stat">{escape(c)}</span>' for c in chips)
    return (f'<div class="rn-celebrate"><div class="rn-big">{icon(icon_name, 34)}</div><h2>{escape(title)}</h2>'
            f'<p>{escape(sub)}</p><div class="rn-gain">{gains}</div></div>')


def tutor_reply(who: str, text: str, sources: list, fmt: Formatter, sources_label: str) -> str:
    """A tutor message; [F3]-style tags become numbered markers with the source underneath."""
    import re
    numbers = {tag: i for i, (tag, _) in enumerate(sources, 1)}
    body = escape(text)
    body = re.sub(r"\[(F\d+)\]", lambda m: (f'<sup title="{escape(dict(sources)[m.group(1)].source)}">'
                                             f'{numbers[m.group(1)]}</sup>' if m.group(1) in numbers else ""), body)
    src = ""
    if sources:
        src = f'<div class="rn-tutor-src"><b>{escape(sources_label)}</b>' + "".join(
            f'<span>{i}. {escape(f.label)}, {escape(f.period)}: {escape(fmt.fact(f))} · {escape(f.source)}</span>'
            for i, (_, f) in enumerate(sources, 1)) + "</div>"
    return (f'<div class="rn-tutor"><div class="rn-tutor-avatar">{icon("spark", 18)}</div>'
            f'<div class="rn-tutor-body"><span class="who">{escape(who)}</span>{body}{src}</div></div>')


def my_message(text: str) -> str:
    return f'<div class="rn-me"><span>{escape(text)}</span></div>'


def footer(text: str) -> None:
    st.html(f'<div class="rn-footer">{escape(text)}</div>')
