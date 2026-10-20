# Plan (approved 2026-10-20)

## Goal
An educational tool for people with little or no investing experience: learn to read
the fundamental charts and numbers behind a company's valuation, with an AI tutor that
adapts to each learner's pace. When "impressive" and "clear to a beginner" conflict,
clear to a beginner wins.

## Decisions
| Topic | Decision |
|---|---|
| Language | English for v1. Every UI string and lesson in locale files; layout RTL-ready, so Hebrew ships with the Israeli retail sector. |
| Progress | Sign in with Google (Streamlit's built-in login); progress in Postgres (Supabase) when deployed, SQLite locally and in tests. Store a hashed ID, never the email. Guest mode keeps progress for the session. |
| AI costs | The owner's key with hard caps: per-learner daily message limit, global daily dollar budget; written content is the fallback. |
| Tutor model | Claude Sonnet 5.5 at low effort (configurable). |
| Engine | Installed as a dependency, used only through `sectors/saas/adapter.py`. |

## Architecture
- `core/` knows nothing about any sector: data types, the `SectorModule` interface,
  universal concepts, chart kinds with "how to read this" layers, the path and game
  engine, the learner model, the tutor, storage, i18n.
- `sectors/<id>/` provides companies and data (through an adapter around that sector's
  engine), metrics, charts, sector concepts, path changes, teaching examples and
  accounting notes for the tutor.
- Every number is a `Fact` with a source. Charts, explanations and the tutor read Facts.

## The game: from Intern to Managing Director
| Stage | Theme | Levels | Boss |
|---|---|---|---|
| 1 Intern | Read the story | revenue chart, growth | Mystery company (name hidden) |
| 2 Analyst | Is it a good business? | margins, (SaaS: SBC), cash vs profit | Cash detective |
| 3 Associate | Worth vs its peers | multiples, (SaaS: fair-multiple line) | Odd one out |
| 4 VP | Worth on its own | DCF, sensitivity | Stress test |
| 5 MD | What the market believes | reverse DCF, capstone | The pitch |

Stars per level (finish / right first time / explained in own words), XP only from
correct answers and explanations, badges per concept (carry across sectors), hint
tokens instead of lives, gentle daily streak, no leaderboards.

## Milestones
1. Chart explanations for one company; review of the core/sector split.
2. Learning path and game (stages, levels, bosses, stars, XP), checks graded locally.
3. Adaptive tutor: ask before tell, re-explanation styles, free questions, grounding
   verifier, cache, budget caps.
4. Progress page, login and database, data snapshot, Streamlit Cloud deploy, README,
   `docs/ADDING_A_SECTOR.md`.
