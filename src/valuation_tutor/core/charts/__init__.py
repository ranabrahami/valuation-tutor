"""The chart kinds the core knows how to draw and explain.

A sector refers to these by key in its ChartDefs. Adding a kind here makes it
available to every sector.
"""

from .base import ChartContext, ChartKind, Guide, Observation
from .history import MarginsChart, ProfitVsCashChart, TrendChart
from .peers import PeerFitChart, PeersChart
from .valuation import ImpliedGrowthChart, PriceVsValueChart, SensitivityChart

KINDS: dict[str, ChartKind] = {k.kind: k for k in (
    TrendChart(), MarginsChart(), ProfitVsCashChart(), PeersChart(), PeerFitChart(),
    PriceVsValueChart(), ImpliedGrowthChart(), SensitivityChart(),
)}

__all__ = ["KINDS", "ChartContext", "ChartKind", "Guide", "Observation"]
