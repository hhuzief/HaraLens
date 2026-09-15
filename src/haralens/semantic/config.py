"""Validated, immutable policy for deterministic semantic inference."""

from typing import Self

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SemanticInferenceConfig(BaseModel):
    """Thresholds used by the explainable rule engine.

    Ratios use non-null observations as their denominator. Content heuristics inspect at
    most ``max_inspection_values`` deterministic, evenly spaced non-null observations.
    Exact counts and uniqueness metrics still use the complete bounded column.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    categorical_max_unique_count: int = Field(default=20, ge=2)
    categorical_max_unique_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    identifier_min_unique_ratio: float = Field(default=0.98, ge=0.0, le=1.0)
    identifier_candidate_min_unique_ratio: float = Field(default=0.80, ge=0.0, le=1.0)
    identifier_min_non_null: int = Field(default=4, ge=2)
    numeric_discrete_max_unique_count: int = Field(default=20, ge=2)
    numeric_discrete_max_unique_ratio: float = Field(default=0.05, ge=0.0, le=1.0)
    free_text_min_average_length: float = Field(default=40.0, gt=0.0)
    free_text_min_unique_ratio: float = Field(default=0.50, ge=0.0, le=1.0)
    free_text_min_whitespace_ratio: float = Field(default=0.50, ge=0.0, le=1.0)
    datetime_min_parse_ratio: float = Field(default=0.90, gt=0.0, le=1.0)
    minimum_confident_non_null: int = Field(default=10, ge=2)
    max_inspection_values: int = Field(default=10_000, ge=10)

    @model_validator(mode="after")
    def validate_identifier_threshold_order(self) -> Self:
        if self.identifier_candidate_min_unique_ratio > self.identifier_min_unique_ratio:
            raise ValueError(
                "identifier_candidate_min_unique_ratio must not exceed identifier_min_unique_ratio"
            )
        return self
