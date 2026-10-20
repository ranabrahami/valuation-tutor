"""The adaptive AI tutor.

The tutor supplies words, not decisions: the learner model decides pacing and
which explanation style comes next; the tutor writes the explanation in that
style for the chart on screen, grounded in its Facts.

Every call goes through _call(), which:
  1. serves shareable replies (re-explanations) from the cache;
  2. enforces the per-learner daily cap and the global daily budget;
  3. checks every number in the reply against the Facts (grounding.check),
     asks once more if any number is unverified, and otherwise returns None
     so the app falls back to the written explanation.
Nothing here names a sector; context comes from the active sector module.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field

from ..fmt import Formatter
from ..sector import Fact
from . import grounding
from .context import TutorContext, sector_block
from .prompts import RULES, SCHEMAS, TASKS
from .store import TutorStore


@dataclass
class TutorReply:
    text: str
    data: dict
    sources: list[tuple[str, Fact]] = field(default_factory=list)   # tags used, in order
    cached: bool = False
    cost_usd: float = 0.0


class Unavailable(Exception):
    """The tutor can't answer right now (cap, budget, refusal, ungrounded reply)."""

    def __init__(self, reason: str):
        super().__init__(reason)
        self.reason = reason       # "learner_cap", "budget", "refused", "ungrounded", "error"


def cost(usage, cfg: dict) -> float:
    def g(name):
        return getattr(usage, name, 0) or 0
    return (g("input_tokens") * cfg["price_input_per_mtok"] + g("output_tokens") * cfg["price_output_per_mtok"]
            + g("cache_read_input_tokens") * cfg["price_cache_read_per_mtok"]
            + g("cache_creation_input_tokens") * cfg["price_cache_write_per_mtok"]) / 1e6


class Tutor:
    def __init__(self, client, cfg: dict, store: TutorStore, fmt: Formatter, language: str = "English"):
        self.client, self.cfg, self.store, self.fmt, self.language = client, cfg, store, fmt, language

    # -- the four jobs ------------------------------------------------------------

    def review_observation(self, ctx: TutorContext, text: str, learner_id: str) -> TutorReply:
        return self._call(ctx, "observation", f"<learner_wrote>\n{text}\n</learner_wrote>", learner_id,
                          extra_texts=[text])

    def reexplain(self, ctx: TutorContext, style: str, question: str, options: list[str], chosen: str | None,
                  learner_id: str) -> TutorReply:
        detail = (f"<question>\n{question}\nOptions: {' | '.join(options)}\n</question>\n"
                  f"<learner_chose>{chosen or '(said they did not get it)'}</learner_chose>\n"
                  f"<style>{style}</style>")
        key = self._key("reexplain", ctx, style, question, chosen or "")
        return self._call(ctx, "reexplain", detail, learner_id, cache_key=key, extra_texts=[question, *options])

    def answer(self, ctx: TutorContext, question: str, history: list[tuple[str, str]],
               learner_id: str) -> TutorReply:
        convo = "\n".join(f"{who}: {msg}" for who, msg in history[-6:])
        detail = f"<conversation>\n{convo or '(none)'}\n</conversation>\n<learner_asks>\n{question}\n</learner_asks>"
        return self._call(ctx, "question", detail, learner_id, extra_texts=[question] + [m for _, m in history])

    def grade_pitch(self, ctx: TutorContext, pitch: str, learner_id: str) -> TutorReply:
        reply = self._call(ctx, "pitch", f"<pitch>\n{pitch}\n</pitch>", learner_id, extra_texts=[pitch])
        reply.data["score"] = max(0, min(4, int(reply.data.get("score", 0))))
        return reply

    # -- plumbing ---------------------------------------------------------------------

    def _key(self, kind: str, ctx: TutorContext, *parts: str) -> str:
        # Only what changes the explanation goes in the key, so learners share replies.
        new_terms = sorted(c.id for c in ctx.concepts if ctx.learner is None or ctx.learner.concept(c.id).seen <= 1)
        raw = json.dumps([self.cfg["model"], self.cfg["prompt_version"], self.language, kind, ctx.sector.id,
                          ctx.company, ctx.chart_title, new_terms, *parts])
        return hashlib.sha256(raw.encode()).hexdigest()

    def request(self, ctx: TutorContext, kind: str, detail: str) -> dict:
        """The exact request body; public so tests and the cost estimate can inspect it."""
        rules = RULES.format(max_words=self.cfg["max_reply_words"], language=self.language)
        return {
            "model": self.cfg["model"],
            "max_tokens": self.cfg["max_tokens"],
            "system": [{"type": "text", "text": rules},
                       {"type": "text", "text": sector_block(ctx.sector), "cache_control": {"type": "ephemeral"}}],
            "messages": [{"role": "user", "content": [
                # Same for every request about this chart: cached across the learner's session.
                {"type": "text", "text": ctx.chart_block(self.fmt), "cache_control": {"type": "ephemeral"}},
                {"type": "text", "text": f"<learner_profile>\n{ctx.learner_profile()}\n</learner_profile>\n"
                                         f"<task>\n{TASKS[kind]}\n</task>\n{detail}"},
            ]}],
            "output_config": {"effort": self.cfg["effort"],
                              "format": {"type": "json_schema", "schema": SCHEMAS[kind]}},
        }

    def _check_caps(self, learner_id: str) -> None:
        if self.store.calls_today(learner_id) >= self.cfg["messages_per_learner_per_day"]:
            raise Unavailable("learner_cap")
        if self.store.spend_today() >= self.cfg["daily_budget_usd"]:
            raise Unavailable("budget")

    def _call(self, ctx: TutorContext, kind: str, detail: str, learner_id: str, cache_key: str | None = None,
              extra_texts: list[str] = ()) -> TutorReply:
        tags = ctx.tags()
        if cache_key and (hit := self.store.get(cache_key)):
            return TutorReply(hit["reply"], hit, self._sources(hit["reply"], tags), cached=True)
        self._check_caps(learner_id)
        body = self.request(ctx, kind, detail)
        texts = ctx.reference_texts() + list(extra_texts)
        spent = 0.0
        for attempt in range(2):
            try:
                message = self.client.messages.create(**body)
            except Exception as exc:       # network, rate limit, overload: fall back, don't crash a lesson
                raise Unavailable("error") from exc
            call_cost = cost(message.usage, self.cfg)
            spent += call_cost
            self.store.record(learner_id, call_cost)
            if message.stop_reason in ("refusal", "max_tokens"):
                raise Unavailable("refused" if message.stop_reason == "refusal" else "error")
            text = "".join(b.text for b in message.content if getattr(b, "type", "") == "text")
            try:
                data = json.loads(text)
            except json.JSONDecodeError as exc:
                raise Unavailable("error") from exc
            check = grounding.check(data.get("reply", ""), tags, texts)
            if check.ok:
                if cache_key:
                    self.store.put(cache_key, data)
                return TutorReply(data["reply"], data, self._sources(data["reply"], tags), cost_usd=spent)
            if attempt == 0:   # one retry, telling the model exactly what was wrong
                problems = ([f"numbers not in your sources: {', '.join(check.unverified)}"] if check.unverified else []) \
                    + ([f"tags that don't exist: {', '.join(check.bad_tags)}"] if check.bad_tags else []) \
                    + (["a recommendation to buy or sell"] if check.recommends_trade else [])
                # The model's turn goes back unchanged (thinking blocks included), then the correction.
                turn = [b.model_dump() if hasattr(b, "model_dump") else b for b in message.content]
                body["messages"] += [{"role": "assistant", "content": turn},
                                     {"role": "user", "content": "Your reply had " + "; ".join(problems)
                                      + ". Rewrite it following the grounding and boundary rules."}]
        raise Unavailable("ungrounded")

    @staticmethod
    def _sources(reply: str, tags: dict[str, Fact]) -> list[tuple[str, Fact]]:
        used = list(dict.fromkeys(grounding.TAG.findall(reply)))
        return [(t, tags[t]) for t in used if t in tags]
