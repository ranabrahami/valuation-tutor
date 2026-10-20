"""What the tutor is allowed to know: the chart on screen and the learner.

Everything comes from the core's own types (the explained chart, the Facts,
the learner model) plus the active sector module. Nothing sector-specific is
written here: the sector's name, accounting standard and notes come from the
module, so the same tutor teaches software today and supermarkets tomorrow.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ..charts import Guide, Observation
from ..fmt import Formatter
from ..learner import Learner
from ..sector import Concept, Fact, SectorModule


@dataclass
class TutorContext:
    sector: SectorModule
    company: str
    chart_title: str
    guide: Guide
    sector_notes: tuple[str, ...]
    observations: list[Observation]
    facts: list[Fact]
    concepts: list[Concept]
    lesson: dict = field(default_factory=dict)
    learner: Learner | None = None
    language: str = "English"

    def tags(self) -> dict[str, Fact]:
        """F1, F2... for each Fact on screen, in a stable order."""
        seen, out = set(), {}
        for f in self.facts:
            if f.id not in seen and not f.missing:
                seen.add(f.id)
                out[f"F{len(out) + 1}"] = f
        return out

    def fact_sheet(self, fmt: Formatter) -> str:
        lines = [f"[{tag}] {f.label}, {f.period}: {fmt.fact(f)} (source: {f.source})" for tag, f in self.tags().items()]
        missing = [f for f in self.facts if f.missing]
        lines += [f"[missing] {f.label}, {f.period}: not available. {f.note}" for f in missing]
        return "\n".join(lines) or "(no numbers on this chart)"

    def learner_profile(self) -> str:
        if self.learner is None:
            return "No history yet: treat every term as new."
        lr = self.learner
        ids = [c.id for c in self.concepts]
        new = [c.name for c in self.concepts if lr.is_new(c.id) or lr.concept(c.id).seen <= 1]
        mastered = [cid for cid, s in lr.concepts.items() if s.mastered]
        struggling = [cid for cid, s in lr.concepts.items() if s.struggles and not s.mastered]
        tried = sorted({s for cid in ids for s in lr.concept(cid).styles_tried})
        return "\n".join([
            f"Terms on this chart that are new to the learner (define each in plain words the first time): "
            f"{', '.join(new) or 'none'}",
            f"Concepts mastered so far: {', '.join(mastered) or 'none yet'}",
            f"Concepts the learner has struggled with: {', '.join(struggling) or 'none'}",
            f"Explanation styles already tried for this chart's concepts: {', '.join(tried) or 'none'}",
        ])

    def chart_block(self, fmt: Formatter) -> str:
        """The per-chart context, identical for every request about this chart (so it caches)."""
        g = self.guide
        obs = "\n".join(f"[O{i}] {o.text}" for i, o in enumerate(self.observations, 1)) or "(none)"
        terms = "\n".join(f"- {c.name}: {c.plain}" + (f" Analogy: {c.analogy}" if c.analogy else "")
                          for c in self.concepts) or "(none)"
        notes = "\n".join(f"- {n}" for n in self.sector_notes) or "(none)"
        lesson = "\n".join(f"{k}: {v}" for k, v in self.lesson.items()) or "(not part of a lesson)"
        return (f"<chart>\nCompany: {self.company}\nChart: {self.chart_title}\n"
                f"How to read it: {g.axes} Look first: {g.look_first} Good sign: {g.good} Warning sign: {g.worrying}\n"
                f"</chart>\n<fact_sheet>\n{self.fact_sheet(fmt)}\n</fact_sheet>\n"
                f"<observations>\n{obs}\n</observations>\n<terms>\n{terms}\n</terms>\n"
                f"<sector_notes>\n{notes}\n</sector_notes>\n<lesson>\n{lesson}\n</lesson>")

    def reference_texts(self) -> list[str]:
        """Texts whose numbers the tutor may repeat (besides the fact sheet)."""
        g = self.guide
        return ([o.text for o in self.observations] + list(self.sector_notes)
                + [g.axes, g.look_first, g.good, g.worrying] + [str(v) for v in self.lesson.values()]
                + [c.plain + " " + c.analogy for c in self.concepts])


def sector_block(sector: SectorModule) -> str:
    """Stable per sector: cached across every learner and chart."""
    notes = "\n".join(f"- {n.title}: {n.text}" for n in sector.accounting_notes()) or "(none)"
    concepts = "\n".join(f"- {c.name}: {c.plain}" for c in sector.concepts()) or "(none)"
    return (f"<sector>\nIndustry: {sector.name}\nAccounting standard: {sector.accounting_standard}\n"
            f"Currency: {sector.currency}\nData as of: {sector.data_as_of}\n"
            f"Accounting and data notes:\n{notes}\nIndustry-specific ideas:\n{concepts}\n</sector>")


def context_for(explainer, data, chart_id: str, learner: Learner | None = None, lesson: dict | None = None,
                language: str = "English") -> TutorContext:
    """Everything on screen for one chart, ready for the tutor."""
    e = explainer.explain(data, chart_id)
    return TutorContext(sector=explainer.sector, company=data.ref.name, chart_title=e.chart.title, guide=e.guide,
                        sector_notes=e.sector_notes, observations=e.observations, facts=e.facts, concepts=e.terms,
                        lesson=dict(lesson or {}), learner=learner, language=language)


def context_for_company(explainer, data, chart_ids: list[str], learner: Learner | None = None,
                        language: str = "English") -> TutorContext:
    """Several charts' worth of context for one company (used to grade the final pitch)."""
    parts = [explainer.explain(data, cid) for cid in chart_ids if cid in explainer.charts]
    parts = [e for e in parts if e.available]
    return TutorContext(
        sector=explainer.sector, company=data.ref.name, chart_title=", ".join(e.chart.title for e in parts),
        guide=parts[0].guide, sector_notes=tuple(n for e in parts for n in e.sector_notes),
        observations=[o for e in parts for o in e.observations], facts=[f for e in parts for f in e.facts],
        concepts=list({c.id: c for e in parts for c in e.terms}.values()), learner=learner, language=language)
