"""Strict recommendation contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class _Model(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


class RecommendationPriority(StrEnum):
    URGENT = "urgent"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class RecommendationAction(StrEnum):
    INVESTIGATE_SOURCE = "investigate_source"
    REVIEW_CAPTURE = "review_capture"
    VERIFY_RECORDS = "verify_records"
    STANDARDIZE_REPRESENTATION = "standardize_representation"
    REVIEW_SEMANTIC_TYPE = "review_semantic_type"
    ESTABLISH_DOMAIN_RULES = "establish_domain_rules"


class Recommendation(_Model):
    recommendation_id: str = Field(min_length=1)
    priority: RecommendationPriority
    action: RecommendationAction
    title: str = Field(min_length=1, max_length=160)
    message: str = Field(min_length=1, max_length=500)
    source_finding_ids: tuple[str, ...] = Field(min_length=1)
    dimension: str
    target_column: str | None = None


class RecommendationResult(_Model):
    quality_run_reference: str
    recommendations: tuple[Recommendation, ...]
