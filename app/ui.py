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
[data-testid="stMainBlockContainer"] {{ max-width: 1180px; padding-top: 1.2rem; padding-bottom: 4rem; }}
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


def footer(text: str) -> None:
    st.html(f'<div class="rn-footer">{escape(text)}</div>')
