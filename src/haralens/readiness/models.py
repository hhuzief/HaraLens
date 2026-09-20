"""Explainable AI-readiness contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class ReadinessBand(StrEnum):
    HIGHLY_READY = "highly_ready"
    READY = "ready"
    PREPARATION_RECOMMENDED = "preparation_recommended"
    SIGNIFICANT_PREPARATION = "significant_preparation_required"
    NOT_READY = "not_ready"


class ReadinessDimension(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    name: str
    score: float = Field(ge=0, le=100)
    weight: float = Field(gt=0, le=1)
    measurement: str
    effect: str
    affected_columns: tuple[str, ...] = ()


class TargetAnalysis(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    target_name: str
    target_kind: str
    missing_count: int = Field(ge=0)
    cardinality: int = Field(ge=0)
    minority_ratio: float | None = Field(default=None, ge=0, le=1)
    constant: bool
    identifier_like: bool
    observations: tuple[str, ...] = ()


class AIReadinessResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    overall_score: float = Field(ge=0, le=100)
    band: ReadinessBand
    dimensions: tuple[ReadinessDimension, ...]
    blockers: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    contributing_factors: tuple[str, ...] = ()
    target: TargetAnalysis | None = None
    methodology_version: str = "1.0.0"
