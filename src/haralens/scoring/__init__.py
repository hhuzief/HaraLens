"""Explainable deterministic health scoring for quality results."""

from haralens.scoring.engine import HealthScorer, severity_prevalence_penalty
from haralens.scoring.models import (
    DimensionHealthScore,
    HealthScoreResult,
    HealthScoringConfig,
    InterpretationBand,
    PenaltyContribution,
    ScoreState,
)

__all__ = [
    "DimensionHealthScore",
    "HealthScoreResult",
    "HealthScorer",
    "HealthScoringConfig",
    "InterpretationBand",
    "PenaltyContribution",
    "ScoreState",
    "severity_prevalence_penalty",
]
