"""Estimate what the AI tutor costs, before anything is billed.

    python scripts/tutor_cost.py              # exact token counts if ANTHROPIC_API_KEY is set (free), else approximate
    python scripts/tutor_cost.py --output 400 # assumed output tokens per reply (thinking + answer)

Builds the real requests for every level's chart and teaching company, counts
their input tokens, and prices one message of each kind, one learner's full
path, and the worst case under the daily caps. Counting tokens is free; this
script never sends a billed request.
"""

from __future__ import annotations

import argparse
import os
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "app"))

from dotenv import load_dotenv  # noqa: E402

from valuation_tutor.core.explain import Explainer  # noqa: E402
from valuation_tutor.core.i18n import Translator  # noqa: E402
from valuation_tutor.core.learner import Learner  # noqa: E402
from valuation_tutor.core.path import LearningPath  # noqa: E402
from valuation_tutor.core.registry import load_sectors, load_settings  # noqa: E402
from valuation_tutor.core.tutor import Tutor  # noqa: E402
from valuation_tutor.core.tutor.context import context_for  # noqa: E402
from valuation_tutor.core.tutor.store import MemoryStore  # noqa: E402

# How a typical learner uses the tutor on one level.
PER_LEVEL = {"observation": 1, "reexplain": 0.5, "question": 1.0}


def count(client, body: dict) -> tuple[int, bool]:
    """Input tokens for a request: exact via the free count_tokens endpoint, else ~3.5 chars/token."""
    if client is not None:
        result = client.messages.count_tokens(model=body["model"], system=body["system"], messages=body["messages"])
        return result.input_tokens, True
    chars = sum(len(b["text"]) for b in body["system"]) + sum(
        len(c["text"]) for m in body["messages"] for c in m["content"])
    return int(chars / 3.5), False


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--output", type=int, default=400, help="assumed output tokens per reply")
    args = parser.parse_args()

    load_dotenv(ROOT / ".env")
    settings = load_settings()
    cfg = settings["tutor"]
    client = None
    if os.getenv("ANTHROPIC_API_KEY"):
        import anthropic
        client = anthropic.Anthropic()

    t = Translator(settings["locale"])
    sector = next(iter(load_sectors(settings).values()))
    ex = Explainer(sector, t)
    path = LearningPath(sector)
    tutor = Tutor(None, cfg, MemoryStore(), ex.fmt)
    learner = Learner()

    tokens: dict[str, list[int]] = {k: [] for k in PER_LEVEL}
    cached_part, exact = [], False
    for step in path.steps:
        if not step.chart_id:
            continue
        ctx = context_for(ex, sector.company_data(step.company), step.chart_id, learner, t.get(f"lessons.{step.id}"))
        details = {"observation": "<learner_wrote>\nThe bars go up every year.\n</learner_wrote>",
                   "reexplain": "<question>\nWhich year was highest?\nOptions: A | B | C\n</question>\n"
                                "<learner_chose>A</learner_chose>\n<style>analogy</style>",
                   "question": "<conversation>\n(none)\n</conversation>\n<learner_asks>\nWhy is this going up?\n"
                               "</learner_asks>"}
        for kind, detail in details.items():
            body = tutor.request(ctx, "question" if kind == "question" else kind, detail)
            n, exact = count(client, body)
            tokens[kind].append(n)
        # Everything up to the chart block's cache marker is reused within a session.
        body = tutor.request(ctx, "observation", "")
        cached_part.append(count(client, {**body, "messages": [{"role": "user", "content": body["messages"][0]["content"][:1]}]})[0])

    price_in, price_out = cfg["price_input_per_mtok"], cfg["price_output_per_mtok"]
    price_read, price_write = cfg["price_cache_read_per_mtok"], cfg["price_cache_write_per_mtok"]
    cached = statistics.mean(cached_part)

    def message_cost(n_in: float, warm: bool) -> float:
        fresh = n_in - cached
        cache = cached * (price_read if warm else price_write)
        return (fresh * price_in + cache + args.output * price_out) / 1e6

    print(f"Model {cfg['model']} · input tokens {'exact (count_tokens, free)' if exact else 'approximate (no key)'}"
          f" · {args.output} output tokens assumed per reply\n")
    print(f"{'Message':<14}{'input tokens':>14}{'first on a chart':>18}{'later (cached)':>16}")
    per_message = {}
    for kind, ns in tokens.items():
        n = statistics.mean(ns)
        per_message[kind] = message_cost(n, warm=True)
        first, later = f"${message_cost(n, False):.4f}", f"${per_message[kind]:.4f}"
        print(f"{kind:<14}{n:>14,.0f}{first:>18}{later:>16}")
    levels = len([s for s in path.steps if s.chart_id])
    full_path = sum(per_message[k] * PER_LEVEL[k] * levels for k in PER_LEVEL)
    worst_day = cfg["messages_per_learner_per_day"] * max(per_message.values())
    print(f"\nOne learner, whole path ({levels} levels, typical use): ${full_path:.2f}")
    print(f"Worst case, one learner, one day ({cfg['messages_per_learner_per_day']} messages): ${worst_day:.2f}")
    print(f"Daily budget cap: ${cfg['daily_budget_usd']:.2f}  -> about "
          f"{cfg['daily_budget_usd'] / full_path:.0f} full-path learners per day")


if __name__ == "__main__":
    main()
