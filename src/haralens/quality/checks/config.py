"""Immutable, versioned defaults for production quality checks."""

from __future__ import annotations

import hashlib
import json
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class ProductionQualityConfig(BaseModel):
    """Deterministic v0.1 thresholds. Percentages are expressed in [0, 100]."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    methodology_version: Literal["1.0.0"] = "1.0.0"
    missingness_low_max: float = Field(ge=0, le=100, default=5.0)
    missingness_medium_max: float = Field(ge=0, le=100, default=20.0)
    missingness_high_max: float = Field(ge=0, le=100, default=40.0)
    high_cardinality_ratio: float = Field(gt=0, le=1, default=0.90)
    high_cardinality_min_observations: int = Field(ge=2, default=10)

    @model_validator(mode="after")
    def ordered_thresholds(self) -> ProductionQualityConfig:
        if not (
            self.missingness_low_max <= self.missingness_medium_max <= self.missingness_high_max
        ):
            raise ValueError("missingness thresholds must be ordered")
        return self

    @property
    def fingerprint(self) -> str:
        payload = json.dumps(self.model_dump(mode="json"), sort_keys=True, separators=(",", ":"))
        return hashlib.sha256(payload.encode()).hexdigest()
