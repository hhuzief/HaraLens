"""Serializable, immutable dataset and column profile models."""

from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

from haralens.profiling.config import ProfilingConfig
from haralens.semantic.models import InferenceConfidence, SemanticType, SemanticTypeCount

PROFILE_VERSION: Literal["1.0.0"] = "1.0.0"


class ProfileWarningCode(StrEnum):
    COLUMN_STATISTICS_UNAVAILABLE = "COLUMN_STATISTICS_UNAVAILABLE"
    DUPLICATE_COUNT_UNAVAILABLE = "DUPLICATE_COUNT_UNAVAILABLE"
    AMBIGUOUS_DATETIME_VALUES_EXCLUDED = "AMBIGUOUS_DATETIME_VALUES_EXCLUDED"
    MIXED_DATETIME_AWARENESS = "MIXED_DATETIME_AWARENESS"
    NON_NUMERIC_VALUES_EXCLUDED = "NON_NUMERIC_VALUES_EXCLUDED"


class ProfileWarning(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    code: ProfileWarningCode
    message: str = Field(min_length=1, max_length=300)
    column_position: int | None = Field(default=None, ge=0)


class ProfileValueKind(StrEnum):
    STRING = "string"
    BOOLEAN = "boolean"
    INTEGER = "integer"
    FLOAT = "float"
    DATE = "date"
    DATETIME = "datetime"


class ProfileValue(BaseModel):
    """A bounded JSON-safe category display, separate from full internal identity.

    Truncated strings carry a SHA-256 fingerprint of the complete string. The fingerprint is
    for deterministic display disambiguation; frequency counting never uses it or the
    truncated ``value``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    kind: ProfileValueKind
    value: str | bool | int | float
    truncated: bool = False
    original_length: int | None = Field(default=None, ge=0)
    fingerprint: str | None = Field(
        default=None,
        min_length=64,
        max_length=64,
        pattern=r"^[0-9a-f]{64}$",
    )


class ValueFrequency(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    value: ProfileValue
    count: int = Field(ge=1)
    percentage: float = Field(ge=0.0, le=100.0)


class NumericStatistics(BaseModel):
    """Finite-only descriptive statistics with explicit sample definitions.

    Variance divides the sum of squared deviations by ``n - ddof``; standard deviation is
    its square root. Quartiles are empirical p=0.25/0.75 quantiles with the configured
    interpolation rule. Skewness is the bias-corrected Fisher-Pearson coefficient for n >= 3.
    Kurtosis is bias-corrected Fisher excess kurtosis for n >= 4. Constant samples return zero
    for both moments. Undefined or non-representable finite statistics are ``None``.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["numeric"] = "numeric"
    finite_count: int = Field(ge=0)
    non_numeric_count: int = Field(ge=0)
    positive_infinity_count: int = Field(ge=0)
    negative_infinity_count: int = Field(ge=0)
    zero_count: int = Field(ge=0)
    positive_count: int = Field(ge=0)
    negative_count: int = Field(ge=0)
    minimum: int | float | None = None
    maximum: int | float | None = None
    mean: float | None = None
    median: float | None = None
    standard_deviation: float | None = None
    variance: float | None = None
    first_quartile: float | None = None
    third_quartile: float | None = None
    interquartile_range: float | None = None
    skewness: float | None = None
    kurtosis: float | None = None


class CategoricalStatistics(BaseModel):
    """Exact typed-category counts with bounded display representations."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["categorical"] = "categorical"
    category_count: int = Field(ge=0)
    mode: ValueFrequency | None = None
    top_values: tuple[ValueFrequency, ...] = ()
    other_value_count: int = Field(ge=0)
    entropy_bits: float | None = Field(default=None, ge=0.0)


class DatetimeStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["datetime"] = "datetime"
    parsed_count: int = Field(ge=0)
    unparsed_count: int = Field(ge=0)
    ambiguous_count: int = Field(ge=0)
    timezone_state: Literal["none", "naive", "aware", "mixed"]
    earliest: str | None = None
    latest: str | None = None
    span_seconds: float | None = Field(default=None, ge=0.0)


class TextStatistics(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    kind: Literal["text"] = "text"
    minimum_length: int | None = Field(default=None, ge=0)
    maximum_length: int | None = Field(default=None, ge=0)
    average_length: float | None = Field(default=None, ge=0.0)
    median_length: float | None = Field(default=None, ge=0.0)
    empty_string_count: int = Field(ge=0)
    whitespace_only_count: int = Field(ge=0)


ColumnStatistics = Annotated[
    NumericStatistics | CategoricalStatistics | DatetimeStatistics | TextStatistics,
    Field(discriminator="kind"),
]


class ColumnProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    column_name: str
    column_position: int = Field(ge=0)
    physical_dtype: str = Field(min_length=1)
    inferred_semantic_type: SemanticType
    semantic_type: SemanticType
    semantic_confidence: InferenceConfidence
    total_count: int = Field(ge=0)
    null_count: int = Field(ge=0)
    non_null_count: int = Field(ge=0)
    missing_percentage: float = Field(ge=0.0, le=100.0)
    unique_count: int | None = Field(default=None, ge=0)
    cardinality_ratio: float | None = Field(default=None, ge=0.0, le=1.0)
    memory_bytes: int = Field(ge=0)
    statistics: ColumnStatistics | None = None
    warnings: tuple[ProfileWarning, ...] = ()


class DatasetSummary(BaseModel):
    """Neutral exact dataset facts.

    ``duplicate_row_count`` counts occurrences after the first equal row, so three equal rows
    contribute two duplicates.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    row_count: int = Field(ge=0)
    column_count: int = Field(ge=0)
    cell_count: int = Field(ge=0)
    memory_bytes: int = Field(ge=0)
    missing_cell_count: int = Field(ge=0)
    missing_percentage: float = Field(ge=0.0, le=100.0)
    duplicate_row_count: int | None = Field(default=None, ge=0)
    duplicate_row_percentage: float | None = Field(default=None, ge=0.0, le=100.0)
    semantic_type_counts: tuple[SemanticTypeCount, ...]
    empty_column_count: int = Field(ge=0)
    constant_column_count: int = Field(ge=0)
    identifier_column_count: int = Field(ge=0)


class ProfilingRunMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    source_kind: Literal["dataframe", "ingestion_result"]
    exact: Literal[True] = True
    total_rows: int = Field(ge=0)
    total_columns: int = Field(ge=0)
    profiled_column_count: int = Field(ge=0)
    failed_column_count: int = Field(ge=0)


class DatasetProfile(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    summary: DatasetSummary
    columns: tuple[ColumnProfile, ...]
    profile_version: Literal["1.0.0"] = PROFILE_VERSION
    semantic_inference_version: str = Field(min_length=1)
    configuration: ProfilingConfig
    run_metadata: ProfilingRunMetadata
    warnings: tuple[ProfileWarning, ...] = ()
