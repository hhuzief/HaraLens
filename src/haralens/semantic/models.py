"""Serializable semantic-inference taxonomy and explainable result models."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from haralens.semantic.config import SemanticInferenceConfig

INFERENCE_VERSION: Literal["1.0.0"] = "1.0.0"


class SemanticType(StrEnum):
    NUMERIC_CONTINUOUS = "numeric_continuous"
    NUMERIC_DISCRETE = "numeric_discrete"
    CATEGORICAL = "categorical"
    BOOLEAN = "boolean"
    DATETIME = "datetime"
    IDENTIFIER = "identifier"
    FREE_TEXT = "free_text"
    CONSTANT = "constant"
    EMPTY = "empty"
    UNKNOWN = "unknown"


class InferenceConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class EvidenceCode(StrEnum):
    ALL_NULL = "ALL_NULL"
    CONSTANT_VALUE = "CONSTANT_VALUE"
    NATIVE_BOOLEAN_DTYPE = "NATIVE_BOOLEAN_DTYPE"
    BOOLEAN_VALUE_SET = "BOOLEAN_VALUE_SET"
    BOOLEAN_NAME_HINT = "BOOLEAN_NAME_HINT"
    BINARY_NUMERIC_SET = "BINARY_NUMERIC_SET"
    BINARY_TEXT_SET = "BINARY_TEXT_SET"
    NATIVE_DATETIME_DTYPE = "NATIVE_DATETIME_DTYPE"
    PYTHON_DATE_VALUES = "PYTHON_DATE_VALUES"
    DATE_LIKE_PATTERN = "DATE_LIKE_PATTERN"
    DATE_PARSE_RATE = "DATE_PARSE_RATE"
    AMBIGUOUS_DATE_FORMAT = "AMBIGUOUS_DATE_FORMAT"
    UUID_PATTERN = "UUID_PATTERN"
    NAME_HINT_IDENTIFIER = "NAME_HINT_IDENTIFIER"
    HIGH_UNIQUENESS = "HIGH_UNIQUENESS"
    IDENTIFIER_CANDIDATE_UNIQUENESS = "IDENTIFIER_CANDIDATE_UNIQUENESS"
    MONOTONIC_INTEGER_SEQUENCE = "MONOTONIC_INTEGER_SEQUENCE"
    STRUCTURED_CODE_PATTERN = "STRUCTURED_CODE_PATTERN"
    NATIVE_NUMERIC_DTYPE = "NATIVE_NUMERIC_DTYPE"
    NUMERIC_INTEGER_ONLY = "NUMERIC_INTEGER_ONLY"
    NUMERIC_FRACTIONAL_VALUES = "NUMERIC_FRACTIONAL_VALUES"
    NATIVE_CATEGORICAL_DTYPE = "NATIVE_CATEGORICAL_DTYPE"
    NAME_HINT_CATEGORICAL = "NAME_HINT_CATEGORICAL"
    LOW_CARDINALITY = "LOW_CARDINALITY"
    HIGH_CARDINALITY = "HIGH_CARDINALITY"
    LONG_TEXT = "LONG_TEXT"
    NAME_HINT_FREE_TEXT = "NAME_HINT_FREE_TEXT"
    HIGH_TEXT_UNIQUENESS = "HIGH_TEXT_UNIQUENESS"
    TEXT_WHITESPACE = "TEXT_WHITESPACE"
    NULL_VALUES_PRESENT = "NULL_VALUES_PRESENT"
    DETERMINISTIC_SAMPLE = "DETERMINISTIC_SAMPLE"
    MIXED_VALUE_TYPES = "MIXED_VALUE_TYPES"
    UNSUPPORTED_PHYSICAL_DTYPE = "UNSUPPORTED_PHYSICAL_DTYPE"
    INFERENCE_ERROR = "INFERENCE_ERROR"


class InferenceWarningCode(StrEnum):
    AMBIGUOUS_DATE_ORDER = "AMBIGUOUS_DATE_ORDER"
    PARTIAL_DATE_PARSE = "PARTIAL_DATE_PARSE"
    BINARY_NUMERIC_AMBIGUITY = "BINARY_NUMERIC_AMBIGUITY"
    BINARY_TEXT_AMBIGUITY = "BINARY_TEXT_AMBIGUITY"
    MULTIPLE_PLAUSIBLE_TYPES = "MULTIPLE_PLAUSIBLE_TYPES"
    DUPLICATE_IDENTIFIER_VALUES = "DUPLICATE_IDENTIFIER_VALUES"
    INSUFFICIENT_OBSERVATIONS = "INSUFFICIENT_OBSERVATIONS"
    UNSUPPORTED_VALUES = "UNSUPPORTED_VALUES"
    COLUMN_INFERENCE_FAILED = "COLUMN_INFERENCE_FAILED"


class InferenceEvidence(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    code: EvidenceCode
    message: str = Field(min_length=1, max_length=300)
    observed: int | float | None = None
    threshold: int | float | None = None


class InferenceWarning(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    code: InferenceWarningCode
    message: str = Field(min_length=1, max_length=300)
    column_position: int | None = Field(default=None, ge=0)


class AlternativeSemanticCandidate(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    semantic_type: SemanticType
    confidence: InferenceConfidence
    evidence_codes: tuple[EvidenceCode, ...] = ()


class ColumnSemanticInference(BaseModel):
    """One primary inference plus metrics, evidence, ambiguity, and override extension."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    column_name: str
    column_position: int = Field(ge=0)
    physical_dtype: str = Field(min_length=1)
    semantic_type: SemanticType
    confidence: InferenceConfidence
    evidence: tuple[InferenceEvidence, ...] = Field(min_length=1)
    nullable: bool
    total_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    non_null_count: int = Field(ge=0)
    unique_count: int | None = Field(default=None, ge=0)
    unique_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    sample_count: int = Field(ge=0)
    sampled: bool
    inference_version: Literal["1.0.0"] = INFERENCE_VERSION
    warnings: tuple[InferenceWarning, ...] = ()
    alternative_candidates: tuple[AlternativeSemanticCandidate, ...] = ()
    user_confirmed_type: SemanticType | None = None

    @property
    def effective_type(self) -> SemanticType:
        """Return a future user override when present, otherwise the inferred type."""

        return self.user_confirmed_type or self.semantic_type


class SemanticTypeCount(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    semantic_type: SemanticType
    count: int = Field(ge=0)


class InferenceRunMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    source_kind: Literal["dataframe", "ingestion_result"]
    total_rows: int = Field(ge=0)
    total_columns: int = Field(ge=0)
    sampled_column_count: int = Field(ge=0)
    failed_column_count: int = Field(ge=0)


class DatasetSemanticProfile(BaseModel):
    """Dataset-level semantic results without broader profiling statistics."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    columns: tuple[ColumnSemanticInference, ...]
    semantic_type_counts: tuple[SemanticTypeCount, ...]
    inference_version: Literal["1.0.0"] = INFERENCE_VERSION
    configuration: SemanticInferenceConfig
    run_metadata: InferenceRunMetadata
    warnings: tuple[InferenceWarning, ...] = ()
