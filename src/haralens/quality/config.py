"""Strict configuration and deterministic fingerprints for quality execution."""

from __future__ import annotations

import hashlib
import json
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from haralens.quality.models import (
    QUALITY_FRAMEWORK_VERSION,
    CheckId,
    QualityDimension,
    SafeName,
    SemanticVersion,
)

ParameterValue = str | int | float | bool
ParameterString = Annotated[str, StringConstraints(max_length=500)]


class _ConfigModel(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)


class QualityConfigParameter(_ConfigModel):
    name: SafeName
    value: ParameterString | int | float | bool


class QualityCheckConfiguration(_ConfigModel):
    check_id: CheckId
    configuration_version: SemanticVersion = "1.0.0"
    parameters: tuple[QualityConfigParameter, ...] = ()

    @field_validator("parameters")
    @classmethod
    def normalize_parameters(
        cls, value: tuple[QualityConfigParameter, ...]
    ) -> tuple[QualityConfigParameter, ...]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("per-check parameter names must be unique")
        return tuple(sorted(value, key=lambda item: item.name))

    def parameter(self, name: str) -> ParameterValue | None:
        return next((item.value for item in self.parameters if item.name == name), None)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json"))


class QualityResourceLimits(_ConfigModel):
    max_registered_checks: int = Field(default=1_000, gt=0)
    max_targets_per_check: int = Field(default=10_000, gt=0)
    max_total_executions: int = Field(default=100_000, gt=0)
    max_rows_per_check: int = Field(default=100_000, gt=0)
    max_regex_values_per_check: int = Field(default=10_000, gt=0)
    max_column_combinations_per_check: int = Field(default=10_000, gt=0)


class QualityFrameworkConfig(_ConfigModel):
    framework_version: Literal["1.0.0"] = QUALITY_FRAMEWORK_VERSION
    enabled_check_ids: tuple[CheckId, ...] = ()
    disabled_check_ids: tuple[CheckId, ...] = ()
    included_dimensions: tuple[QualityDimension, ...] = ()
    fail_fast_internal_errors: bool = False
    check_configurations: tuple[QualityCheckConfiguration, ...] = ()
    resources: QualityResourceLimits = Field(default_factory=QualityResourceLimits)

    @field_validator("enabled_check_ids", "disabled_check_ids")
    @classmethod
    def normalize_check_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("check ID lists cannot contain duplicates")
        return tuple(sorted(value))

    @field_validator("included_dimensions")
    @classmethod
    def normalize_dimensions(
        cls, value: tuple[QualityDimension, ...]
    ) -> tuple[QualityDimension, ...]:
        if len(value) != len(set(value)):
            raise ValueError("included dimensions cannot contain duplicates")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("check_configurations")
    @classmethod
    def normalize_check_configurations(
        cls, value: tuple[QualityCheckConfiguration, ...]
    ) -> tuple[QualityCheckConfiguration, ...]:
        ids = [item.check_id for item in value]
        if len(ids) != len(set(ids)):
            raise ValueError("only one configuration is allowed per check ID")
        return tuple(sorted(value, key=lambda item: item.check_id))

    @model_validator(mode="after")
    def validate_enable_disable_overlap(self) -> Self:
        overlap = set(self.enabled_check_ids) & set(self.disabled_check_ids)
        if overlap:
            raise ValueError("a check cannot be both explicitly enabled and disabled")
        return self

    def configuration_for(self, check_id: str) -> QualityCheckConfiguration | None:
        return next((item for item in self.check_configurations if item.check_id == check_id), None)

    @property
    def fingerprint(self) -> str:
        return _fingerprint(self.model_dump(mode="json"))


def _fingerprint(value: object) -> str:
    encoded = json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    ).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()
