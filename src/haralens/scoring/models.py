"""Strict serializable scoring contracts."""

from __future__ import annotations

import hashlib
import json
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from haralens.quality.models import QualityDimension, Severity


class ScoreState(StrEnum):
    EVALUATED = "evaluated"
    NOT_EVALUATED = "not_evaluated"


class InterpretationBand(StrEnum):
    EXCELLENT = "excellent"
    GOOD = "good"
    NEEDS_ATTENTION = "needs_attention"
    POOR = "poor"
    CRITICAL = "critical"


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


class HealthScoringConfig(_Model):
    methodology_version: Literal["1.0.0"] = "1.0.0"
    completeness_weight: float = Field(gt=0, default=0.20)
    uniqueness_weight: float = Field(gt=0, default=0.15)
    validity_weight: float = Field(gt=0, default=0.20)
    consistency_weight: float = Field(gt=0, default=0.15)
    integrity_weight: float = Field(gt=0, default=0.20)
    analytical_readiness_weight: float = Field(gt=0, default=0.10)

    @property
    def weights(self) -> dict[QualityDimension, float]:
        return {
            QualityDimension.COMPLETENESS: self.completeness_weight,
            QualityDimension.UNIQUENESS: self.uniqueness_weight,
            QualityDimension.VALIDITY: self.validity_weight,
            QualityDimension.CONSISTENCY: self.consistency_weight,
            QualityDimension.INTEGRITY: self.integrity_weight,
            QualityDimension.ANALYTICAL_READINESS: self.analytical_readiness_weight,
        }

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()


class PenaltyContribution(_Model):
    finding_id: str
    check_id: str
    dimension: QualityDimension
    severity: Severity
    finding_family: str
    penalty_group: str
    target_key: str
    prevalence: float = Field(ge=0, le=1)
    penalty_points: float = Field(ge=0, le=100)
    explanation: str = Field(min_length=1, max_length=300)
    applied: bool = True
    linked_to_finding_id: str | None = None


class DimensionHealthScore(_Model):
    dimension: QualityDimension
    state: ScoreState
    score: float | None = Field(default=None, ge=0, le=100)
    executed_check_count: int = Field(ge=0)
    effective_weight: float | None = Field(default=None, ge=0, le=1)
    penalties: tuple[PenaltyContribution, ...] = ()


class HealthScoreResult(_Model):
    scoring_methodology_version: Literal["1.0.0"] = "1.0.0"
    quality_run_reference: str
    configuration_fingerprint: str
    dimensions: tuple[DimensionHealthScore, ...]
    overall_score: float | None = Field(default=None, ge=0, le=100)
    overall_state: ScoreState
    interpretation: InterpretationBand | None = None
