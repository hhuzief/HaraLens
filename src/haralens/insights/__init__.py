"""Public automated insight API."""

from haralens.insights.identifiers import build_insight_id, canonicalize_identifier_component
from haralens.insights.models import Insight, InsightFamily, InsightResult
from haralens.insights.service import generate_insights

__all__ = [
    "Insight",
    "InsightFamily",
    "InsightResult",
    "build_insight_id",
    "canonicalize_identifier_component",
    "generate_insights",
]
