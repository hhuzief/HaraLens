"""Safe, structured deterministic insight contracts."""

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class InsightFamily(StrEnum):
    QUALITY = "quality"
    READINESS = "readiness"
    DISTRIBUTION = "distribution"
    MISSINGNESS = "missingness"
    CARDINALITY = "cardinality"
    CORRELATION = "correlation"
    OUTLIERS = "outliers"
    TARGET = "target"
    STRUCTURE = "structure"


class Insight(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    id: str = Field(pattern=r"^[A-Z0-9_]+$")
    family: InsightFamily
    importance: int = Field(ge=1, le=100)
    title: str = Field(min_length=1, max_length=120)
    message: str = Field(min_length=1, max_length=500)
    supporting_metrics: dict[str, float | int | str] = {}
    affected_targets: tuple[str, ...] = ()


class InsightResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    insights: tuple[Insight, ...]
    display_limit: int = Field(gt=0)
