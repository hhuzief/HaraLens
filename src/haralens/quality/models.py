"""Strict, serializable models for the Phase 1E quality-check framework."""

from __future__ import annotations

import math
from enum import StrEnum
from typing import Annotated, Literal, Self

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    StringConstraints,
    field_validator,
    model_validator,
)

from haralens.semantic.models import SemanticType

QUALITY_FRAMEWORK_VERSION: Literal["1.0.0"] = "1.0.0"
QUALITY_DIMENSION_TAXONOMY_VERSION: Literal["1.0.0"] = "1.0.0"

CheckId = Annotated[
    str,
    StringConstraints(pattern=r"^DQ_[A-Z0-9]+(?:_[A-Z0-9]+)*$", min_length=4, max_length=100),
]
SemanticVersion = Annotated[
    str, StringConstraints(pattern=r"^[0-9]+\.[0-9]+\.[0-9]+$", max_length=30)
]
SafeCode = Annotated[
    str, StringConstraints(pattern=r"^[A-Z][A-Z0-9_]*$", min_length=1, max_length=100)
]
SafeName = Annotated[
    str, StringConstraints(pattern=r"^[a-z][a-z0-9_]*$", min_length=1, max_length=100)
]
SafeMessage = Annotated[str, StringConstraints(min_length=1, max_length=500)]
Fingerprint = Annotated[str, StringConstraints(pattern=r"^[0-9a-f]{64}$")]
MetricScalar = int | float | bool


class _QualityModel(BaseModel):
    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
        strict=True,
        allow_inf_nan=False,
        validate_default=True,
    )


class QualityDimension(StrEnum):
    COMPLETENESS = "completeness"
    UNIQUENESS = "uniqueness"
    VALIDITY = "validity"
    CONSISTENCY = "consistency"
    INTEGRITY = "integrity"
    ANALYTICAL_READINESS = "analytical_readiness"


class CheckScope(StrEnum):
    DATASET = "dataset"
    COLUMN = "column"
    MULTI_COLUMN = "multi_column"


class CheckExecutionStatus(StrEnum):
    EXECUTED = "executed"
    SKIPPED = "skipped"
    NOT_APPLICABLE = "not_applicable"
    ERROR = "error"


class QualityOutcome(StrEnum):
    PASS = "pass"  # noqa: S105 - result status, not a credential
    FAIL = "fail"
    NOT_EVALUATED = "not_evaluated"


class Severity(StrEnum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFORMATIONAL = "informational"


class PopulationBasis(StrEnum):
    TOTAL_ROWS = "total_rows"
    NON_NULL_ROWS = "non_null_rows"
    TOTAL_CELLS = "total_cells"
    DISTINCT_VALUES = "distinct_values"
    APPLICABLE_VALUES = "applicable_values"
    CUSTOM = "custom"


class ConditionOperator(StrEnum):
    LESS_THAN_OR_EQUAL = "less_than_or_equal"
    GREATER_THAN_OR_EQUAL = "greater_than_or_equal"
    EQUAL = "equal"
    NOT_EQUAL = "not_equal"
    IN_ALLOWED_SET = "in_allowed_set"
    MATCHES_RULE = "matches_rule"
    CUSTOM = "custom"


class EvidenceSource(StrEnum):
    TABLE = "table"
    SEMANTIC_PROFILE = "semantic_profile"
    DATASET_PROFILE = "dataset_profile"
    COLUMN_PROFILE = "column_profile"
    CONFIGURATION = "configuration"


class CheckPrerequisite(StrEnum):
    TABLE = "table"
    SEMANTIC_PROFILE = "semantic_profile"
    DATASET_PROFILE = "dataset_profile"
    INGESTION_METADATA = "ingestion_metadata"


class QualityCheckDefinition(_QualityModel):
    check_id: CheckId
    check_version: SemanticVersion
    display_name: str = Field(min_length=1, max_length=120)
    dimension: QualityDimension
    scope: CheckScope
    description: str = Field(min_length=1, max_length=500)
    supported_semantic_types: tuple[SemanticType, ...] = ()
    tags: tuple[SafeName, ...] = ()
    prerequisites: tuple[CheckPrerequisite, ...] = (
        CheckPrerequisite.TABLE,
        CheckPrerequisite.SEMANTIC_PROFILE,
        CheckPrerequisite.DATASET_PROFILE,
    )
    default_enabled: bool = True

    @field_validator("supported_semantic_types")
    @classmethod
    def normalize_semantic_types(cls, value: tuple[SemanticType, ...]) -> tuple[SemanticType, ...]:
        if len(value) != len(set(value)):
            raise ValueError("supported semantic types must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @field_validator("tags")
    @classmethod
    def normalize_tags(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("tags must be unique")
        return tuple(sorted(value))

    @field_validator("prerequisites")
    @classmethod
    def normalize_prerequisites(
        cls, value: tuple[CheckPrerequisite, ...]
    ) -> tuple[CheckPrerequisite, ...]:
        if len(value) != len(set(value)):
            raise ValueError("prerequisites must be unique")
        return tuple(sorted(value, key=lambda item: item.value))

    @model_validator(mode="after")
    def validate_scope_metadata(self) -> Self:
        if self.scope is CheckScope.DATASET and self.supported_semantic_types:
            raise ValueError("dataset checks cannot declare supported column semantic types")
        return self


class QualityTarget(_QualityModel):
    scope: CheckScope
    column_name: str | None = None
    column_position: int | None = Field(default=None, ge=0)
    column_names: tuple[str, ...] = ()
    column_positions: tuple[int, ...] = ()

    @model_validator(mode="after")
    def validate_target_shape(self) -> Self:
        if self.scope is CheckScope.DATASET:
            if (
                self.column_name is not None
                or self.column_position is not None
                or self.column_names
                or self.column_positions
            ):
                raise ValueError("dataset targets cannot contain columns")
        elif self.scope is CheckScope.COLUMN:
            if (
                self.column_name is None
                or self.column_position is None
                or self.column_names
                or self.column_positions
            ):
                raise ValueError("column targets require exactly one name and position")
        elif (
            self.column_name is not None
            or self.column_position is not None
            or len(self.column_names) < 2
            or len(self.column_names) != len(self.column_positions)
            or len(set(self.column_positions)) != len(self.column_positions)
        ):
            raise ValueError("multi-column targets require at least two unique physical positions")
        return self


class AffectedPopulation(_QualityModel):
    affected_count: int = Field(ge=0)
    population_count: int = Field(ge=0)
    affected_percentage: float | None = Field(ge=0.0, le=100.0)
    basis: PopulationBasis
    basis_description: str | None = Field(default=None, min_length=1, max_length=200)

    @classmethod
    def from_counts(
        cls,
        affected_count: int,
        population_count: int,
        basis: PopulationBasis,
        *,
        basis_description: str | None = None,
    ) -> AffectedPopulation:
        percentage = affected_count / population_count * 100.0 if population_count else None
        return cls(
            affected_count=affected_count,
            population_count=population_count,
            affected_percentage=percentage,
            basis=basis,
            basis_description=basis_description,
        )

    @model_validator(mode="after")
    def validate_population(self) -> Self:
        if self.affected_count > self.population_count:
            raise ValueError("affected_count cannot exceed population_count")
        if self.population_count == 0:
            if self.affected_percentage is not None:
                raise ValueError("zero populations require an undefined percentage")
        elif self.affected_percentage is None:
            raise ValueError("non-zero populations require an affected percentage")
        else:
            expected = self.affected_count / self.population_count * 100.0
            if not math.isclose(
                self.affected_percentage,
                expected,
                rel_tol=1e-12,
                abs_tol=1e-12,
            ):
                raise ValueError("affected_percentage must match the supplied counts")
        if self.basis is PopulationBasis.CUSTOM and self.basis_description is None:
            raise ValueError("custom population basis requires a description")
        if self.basis is not PopulationBasis.CUSTOM and self.basis_description is not None:
            raise ValueError("basis_description is only valid for custom populations")
        return self


class QualityCondition(_QualityModel):
    metric_name: SafeName
    operator: ConditionOperator
    expected: MetricScalar | None = None
    description: str | None = Field(default=None, min_length=1, max_length=300)

    @model_validator(mode="after")
    def validate_condition(self) -> Self:
        if self.operator is ConditionOperator.CUSTOM:
            if self.description is None:
                raise ValueError("custom conditions require a safe description")
        elif self.expected is None:
            raise ValueError("non-custom conditions require an expected scalar")
        return self


class QualityEvidence(_QualityModel):
    metric_name: SafeName
    source: EvidenceSource
    observed: MetricScalar | None = None
    expected: MetricScalar | None = None
    operator: ConditionOperator | None = None
    profile_field: SafeName | None = None
    description: str | None = Field(default=None, min_length=1, max_length=300)


class MethodologyMetadata(_QualityModel):
    name: SafeName
    value: Annotated[str, StringConstraints(max_length=200)] | int | float | bool


class FindingDraft(_QualityModel):
    severity: Severity
    message: SafeMessage
    affected_population: AffectedPopulation | None = None
    condition: QualityCondition | None = None
    evidence: tuple[QualityEvidence, ...] = Field(min_length=1)
    methodology: tuple[MethodologyMetadata, ...] = ()
    warning_codes: tuple[SafeCode, ...] = ()

    @field_validator("severity")
    @classmethod
    def validate_failure_severity(cls, value: Severity) -> Severity:
        if value is Severity.INFORMATIONAL:
            raise ValueError("informational severity is not valid for a failed finding")
        return value

    @field_validator("methodology")
    @classmethod
    def normalize_methodology(
        cls, value: tuple[MethodologyMetadata, ...]
    ) -> tuple[MethodologyMetadata, ...]:
        names = [item.name for item in value]
        if len(names) != len(set(names)):
            raise ValueError("methodology names must be unique")
        return tuple(sorted(value, key=lambda item: item.name))

    @field_validator("warning_codes")
    @classmethod
    def normalize_warning_codes(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(value) != len(set(value)):
            raise ValueError("warning codes must be unique")
        return tuple(sorted(value))


class CheckEvaluation(_QualityModel):
    outcome: QualityOutcome
    findings: tuple[FindingDraft, ...] = ()

    @model_validator(mode="after")
    def validate_evaluation(self) -> Self:
        if self.outcome is QualityOutcome.NOT_EVALUATED:
            raise ValueError("checks may return only pass or fail evaluations")
        if self.outcome is QualityOutcome.PASS and self.findings:
            raise ValueError("a passed evaluation cannot contain findings")
        if self.outcome is QualityOutcome.FAIL and not self.findings:
            raise ValueError("a failed evaluation requires at least one finding")
        return self


class CheckApplicability(_QualityModel):
    applicable: bool
    reason_code: SafeCode | None = None
    message: SafeMessage | None = None

    @model_validator(mode="after")
    def validate_applicability(self) -> Self:
        if self.applicable and (self.reason_code is not None or self.message is not None):
            raise ValueError("applicable checks cannot carry a non-applicability reason")
        if not self.applicable and (self.reason_code is None or self.message is None):
            raise ValueError("non-applicable checks require a code and message")
        return self


class QualityFinding(_QualityModel):
    finding_id: Fingerprint
    run_reference: Fingerprint
    check_id: CheckId
    check_version: SemanticVersion
    dimension: QualityDimension
    scope: CheckScope
    target: QualityTarget
    outcome: QualityOutcome
    severity: Severity
    message: SafeMessage
    affected_population: AffectedPopulation | None = None
    condition: QualityCondition | None = None
    evidence: tuple[QualityEvidence, ...]
    methodology: tuple[MethodologyMetadata, ...] = ()
    warning_codes: tuple[SafeCode, ...] = ()

    @field_validator("severity")
    @classmethod
    def validate_failure_severity(cls, value: Severity) -> Severity:
        if value is Severity.INFORMATIONAL:
            raise ValueError("informational severity is not valid for a failed finding")
        return value

    @model_validator(mode="after")
    def validate_failure_outcome(self) -> Self:
        if self.outcome is not QualityOutcome.FAIL:
            raise ValueError("quality findings require a failed outcome")
        return self


class CheckExecutionResult(_QualityModel):
    check_id: CheckId
    check_version: SemanticVersion
    dimension: QualityDimension
    scope: CheckScope
    target: QualityTarget | None
    execution_status: CheckExecutionStatus
    outcome: QualityOutcome
    findings: tuple[QualityFinding, ...] = ()
    configuration_fingerprint: Fingerprint
    status_code: SafeCode | None = None
    message: SafeMessage | None = None

    @model_validator(mode="after")
    def validate_execution(self) -> Self:
        if self.target is not None and self.target.scope is not self.scope:
            raise ValueError("execution target scope must match check scope")
        if self.execution_status is CheckExecutionStatus.EXECUTED:
            if self.outcome is QualityOutcome.NOT_EVALUATED:
                raise ValueError("executed checks require a pass or fail outcome")
            if self.status_code is not None or self.message is not None:
                raise ValueError("executed checks cannot carry status details")
            if self.outcome is QualityOutcome.PASS and self.findings:
                raise ValueError("passed executions cannot contain findings")
            if self.outcome is QualityOutcome.FAIL and not self.findings:
                raise ValueError("failed executions require at least one finding")
        else:
            if self.outcome is not QualityOutcome.NOT_EVALUATED or self.findings:
                raise ValueError("unexecuted checks must be not_evaluated without findings")
            if self.status_code is None or self.message is None:
                raise ValueError("unexecuted checks require a status code and message")
        for finding in self.findings:
            if (
                finding.check_id != self.check_id
                or finding.check_version != self.check_version
                or finding.dimension is not self.dimension
                or finding.scope is not self.scope
                or finding.target != self.target
            ):
                raise ValueError("finding identity must match its execution")
        return self


class DimensionRunSummary(_QualityModel):
    dimension: QualityDimension
    total_executions: int = Field(ge=0)
    executed: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    errors: int = Field(ge=0)
    finding_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        _validate_summary_counts(self)
        return self


class QualityRunSummary(_QualityModel):
    total_executions: int = Field(ge=0)
    executed: int = Field(ge=0)
    passed: int = Field(ge=0)
    failed: int = Field(ge=0)
    skipped: int = Field(ge=0)
    not_applicable: int = Field(ge=0)
    errors: int = Field(ge=0)
    finding_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        _validate_summary_counts(self)
        return self


class QualityRunMetadata(_QualityModel):
    quality_framework_version: Literal["1.0.0"] = QUALITY_FRAMEWORK_VERSION
    dimension_taxonomy_version: Literal["1.0.0"] = QUALITY_DIMENSION_TAXONOMY_VERSION
    run_reference: Fingerprint
    configuration_fingerprint: Fingerprint
    registry_fingerprint: Fingerprint
    registered_check_count: int = Field(ge=0)
    enabled_check_count: int = Field(ge=0)
    result_count: int = Field(ge=0)

    @model_validator(mode="after")
    def validate_counts(self) -> Self:
        if self.enabled_check_count > self.registered_check_count:
            raise ValueError("enabled_check_count cannot exceed registered_check_count")
        return self


class QualityRunResult(_QualityModel):
    executions: tuple[CheckExecutionResult, ...]
    summary: QualityRunSummary
    dimensions: tuple[DimensionRunSummary, ...]
    metadata: QualityRunMetadata

    @model_validator(mode="after")
    def validate_result_integrity(self) -> Self:
        if tuple(item.dimension for item in self.dimensions) != tuple(QualityDimension):
            raise ValueError("dimension summaries must contain the complete taxonomy in order")
        if self.metadata.result_count != len(self.executions):
            raise ValueError("result_count must match the execution collection")
        fields = (
            "total_executions",
            "executed",
            "passed",
            "failed",
            "skipped",
            "not_applicable",
            "errors",
            "finding_count",
        )
        for field in fields:
            total = sum(getattr(item, field) for item in self.dimensions)
            if total != getattr(self.summary, field):
                raise ValueError("dimension counts must add up to the run summary")
        for execution in self.executions:
            for finding in execution.findings:
                if finding.run_reference != self.metadata.run_reference:
                    raise ValueError("finding run references must match run metadata")
        return self


def _validate_summary_counts(summary: DimensionRunSummary | QualityRunSummary) -> None:
    if summary.total_executions != (
        summary.executed + summary.skipped + summary.not_applicable + summary.errors
    ):
        raise ValueError("execution status counts must add up to total_executions")
    if summary.executed != summary.passed + summary.failed:
        raise ValueError("pass and fail counts must add up to executed")
