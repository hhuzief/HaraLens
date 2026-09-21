"""Frontend-independent, bounded visual summaries of canonical analysis results."""

from . import prepare
from .render import chart_document, render_chart

__all__ = ["prepare", "chart_document", "render_chart"]
