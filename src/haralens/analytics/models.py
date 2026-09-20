"""Bounded, deterministic analytical result models."""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class AnalyticsModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


class NumericAnalytics(AnalyticsModel):
    column_name: str
    finite_count: int = Field(ge=0)
    outlier_count: int = Field(ge=0)
    outlier_percentage: float = Field(ge=0, le=100)
    lower_bound: float | None = None
    upper_bound: float | None = None
    skewness_interpretation: str


class CategoricalAnalytics(AnalyticsModel):
    column_name: str
    cardinality: int = Field(ge=0)
    top_category_share: float | None = Field(default=None, ge=0, le=100)
    entropy_bits: float | None = Field(default=None, ge=0)
    high_cardinality: bool


class CorrelationPair(AnalyticsModel):
    left: str
    right: str
    coefficient: float = Field(ge=-1, le=1)
    observation_count: int = Field(ge=0)


class AnalyticsResult(AnalyticsModel):
    methodology_version: str = "1.0.0"
    numeric: tuple[NumericAnalytics, ...] = ()
    categorical: tuple[CategoricalAnalytics, ...] = ()
    correlations: tuple[CorrelationPair, ...] = ()
    correlation_column_limit: int = Field(gt=0)
    strong_correlation_threshold: float = Field(gt=0, le=1)
