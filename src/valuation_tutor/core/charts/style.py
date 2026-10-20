"""Chart colours and shared styling.

Values from the validated reference palette (colour-blind safe and >= 3:1
contrast on the light surface; checked with the dataviz validator):
  FOCUS / SECOND   the two categorical slots, for one or two series
  CONTEXT          peers and anything that is background, not the subject
Beginner rules applied everywhere: one y-axis per chart, at most two series,
thin marks, recessive grid, direct labels instead of a number on every point.
"""

import altair as alt

FOCUS = "#2a78d6"      # the company being studied / the main series
SECOND = "#eb6834"     # a second series, when a chart compares two things
CONTEXT = "#c3c2b7"    # peers, gaps, background marks
FOCUS_LIGHT = "#9cc3f0"
INK = "#0b0b0b"
INK_SECONDARY = "#52514e"
MUTED = "#898781"
GRID = "#e1e0d9"
SURFACE = "#fcfcfb"

# Diverging scale for "above vs below today's price": blue <-> gray <-> red.
ABOVE = "#2a78d6"
NEUTRAL = "#f0efec"
BELOW = "#e34948"

HEIGHT = 300


def finish(chart: alt.Chart, height: int = HEIGHT) -> alt.Chart:
    """Common chart chrome: recessive grid and axes, no chart border."""
    return (chart.properties(height=height)
            .configure_view(strokeWidth=0)
            .configure_axis(gridColor=GRID, domainColor=CONTEXT, tickColor=CONTEXT,
                            labelColor=INK_SECONDARY, titleColor=INK_SECONDARY,
                            labelFontSize=12, titleFontSize=12, titleFontWeight="normal")
            .configure_legend(labelColor=INK_SECONDARY, titleColor=INK_SECONDARY,
                              orient="top", labelFontSize=12))
