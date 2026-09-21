"""Dashboard-only tokens and supported Streamlit layout primitives.

Report styles remain independent of this dark application surface.
"""

import streamlit as st

DARK = {
    "background": "#0e1e29",
    "surface": "#203646",
    "text": "#f1f5f9",
    "muted": "#b3c4d3",
    "border": "#304b5e",
    "health": "#32cf96",
    "readiness": "#429dff",
    "neutral": "#429dff",
    "warning": "#ff9a45",
    "critical": "#ff535b",
    "medium": "#f4cc53",
    "secondary": "#80cbd7",
}

DASHBOARD_CSS = """
html, body { margin: 0; background: transparent; color-scheme: dark; }
.hl-chart { color-scheme: dark; box-sizing: border-box; margin: 0;
  min-height: 330px; padding: 16px; border-radius: 8px; }
.hl-chart h3 { font-size: 16px; line-height: 1.3; margin-bottom: 10px; }
.hl-chart .hl-plot { height: 245px; }
.hl-chart svg { min-width: 0; width: 100%; height: 100%; }
.hl-chart figcaption { font-size: 12px; line-height: 1.4; }
.hl-chart .hl-empty { min-height: 200px; box-sizing: border-box; }
.hl-chart.matrix .hl-plot { height: 330px; }
.hl-chart.matrix { min-height: 420px; }
.hl-chart.matrix svg { min-width: 580px; height: auto; }
.hl-chart.dense .hl-plot { overflow-y: auto; }
.hl-chart.dense svg { height: auto; min-height: 245px; }
"""


def page_header(title: str, description: str) -> None:
    st.title(title)
    st.caption(description)
