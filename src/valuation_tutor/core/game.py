"""Game rules: XP, stars, ranks, badges, hint tokens, streaks.

Designed to motivate beginners without punishing them:
  * XP only comes from correct answers and from writing what you see, never
    from clicking quickly, so the fastest route up is understanding.
  * Mistakes cost nothing. There are no lives; a wrong answer unlocks a
    different explanation. Hint tokens remove one wrong option.
  * Stars per level: 1 for finishing, 1 for answering right the first time,
    1 for putting what you see into your own words (from milestone 3 the
    tutor judges that; until then writing a real attempt earns it).
  * No leaderboards: comparing yourself with others discourages beginners.
"""

from __future__ import annotations

# --- XP ---------------------------------------------------------------------
XP_CORRECT_FIRST_TRY = 20
XP_CORRECT_AFTER_RETRY = 10
XP_OBSERVATION = 5
XP_BOSS_PASSED = 50
XP_PER_PITCH_POINT = 10          # final boss: the tutor scores the pitch 0-4

# --- Ranks: one promotion per boss beaten -----------------------------------
RANKS = ["intern", "analyst", "associate", "vp", "director", "md"]

# --- Bosses ------------------------------------------------------------------
BOSS_QUESTIONS = 3
BOSS_PASS_MARK = 2              # correct answers out of BOSS_QUESTIONS

# --- Hints and streaks -------------------------------------------------------
STARTING_HINTS = 3
HINTS_PER_BOSS = 1
MIN_OBSERVATION_WORDS = 6       # "own words" star before the tutor can judge quality

# --- Badges: earned when every listed concept is mastered --------------------
# Concept ids are core ids, so a badge earned in one sector stays earned in all.
BADGES: dict[str, tuple[str, ...]] = {
    "growth_spotter": ("revenue", "growth"),
    "margin_reader": ("margin", "gross_margin", "operating_margin"),
    "cash_detective": ("profit", "free_cash_flow"),
    "multiple_master": ("multiple", "peer_group"),
    "dcf_decoder": ("dcf", "discount_rate", "sensitivity"),
    "myth_buster": ("implied_expectations",),
}


def rank_for(bosses_passed: int) -> str:
    return RANKS[min(bosses_passed, len(RANKS) - 1)]


def stars_for(finished: bool, right_first_time: bool, own_words: bool) -> int:
    return int(finished) + int(finished and right_first_time) + int(finished and own_words)


def counts_as_own_words(text: str) -> bool:
    return len(text.split()) >= MIN_OBSERVATION_WORDS
