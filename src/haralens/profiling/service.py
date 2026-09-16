"""Deterministic, semantic-aware dataset and column profiling service."""

from __future__ import annotations

import math
from collections import Counter
from datetime import UTC, date, datetime
from hashlib import sha256
from numbers import Integral, Real
from typing import Any, Literal

import pandas as pd

from haralens.ingestion.models import IngestionResult
from haralens.profiling.config import ProfilingConfig
from haralens.profiling.errors import ProfilingError, ProfilingErrorCode
from haralens.profiling.models import (
    CategoricalStatistics,
    ColumnProfile,
    ColumnStatistics,
    DatasetProfile,
    DatasetSummary,
    DatetimeStatistics,
    NumericStatistics,
    ProfileValue,
    ProfileValueKind,
    ProfileWarning,
    ProfileWarningCode,
    ProfilingRunMetadata,
    TextStatistics,
    ValueFrequency,
)
from haralens.semantic.models import (
    ColumnSemanticInference,
    DatasetSemanticProfile,
    SemanticType,
    SemanticTypeCount,
)


class ProfilingService:
    """Build exact profiles from a table and its matching semantic profile."""

    def __init__(self, config: ProfilingConfig | None = None) -> None:
        self.config = config or ProfilingConfig()

    def profile(
        self,
        source: pd.DataFrame | IngestionResult,
        semantic_profile: DatasetSemanticProfile,
    ) -> DatasetProfile:
        table, source_kind = self._source_table(source)
        self._validate_input(table, source, semantic_profile)

        dataset_warnings: list[ProfileWarning] = []
        duplicate_count, duplicate_percentage = _duplicate_summary(table, dataset_warnings)
        columns: list[ColumnProfile] = []
        failed_count = 0

        for position, semantic in enumerate(semantic_profile.columns):
            series = table.iloc[:, position]
            column_warnings: list[ProfileWarning] = []
            try:
                statistics = self._statistics(series, semantic, column_warnings)
            except Exception:
                statistics = None
                failed_count += 1
                warning = ProfileWarning(
                    code=ProfileWarningCode.COLUMN_STATISTICS_UNAVAILABLE,
                    message="Specialized statistics could not be computed for this column.",
                    column_position=position,
                )
                column_warnings.append(warning)
                dataset_warnings.append(warning)

            unique_count, cardinality_ratio = _cardinality(series, semantic, statistics)
            columns.append(
                ColumnProfile(
                    column_name=semantic.column_name,
                    column_position=position,
                    physical_dtype=str(series.dtype),
                    inferred_semantic_type=semantic.semantic_type,
                    semantic_type=semantic.effective_type,
                    semantic_confidence=semantic.confidence,
                    total_count=len(series),
                    null_count=semantic.null_count,
                    non_null_count=semantic.non_null_count,
                    missing_percentage=_percentage(semantic.null_count, len(series)),
                    unique_count=unique_count,
                    cardinality_ratio=cardinality_ratio,
                    memory_bytes=int(series.memory_usage(index=False, deep=True)),
                    statistics=statistics,
                    warnings=tuple(column_warnings),
                )
            )

        type_counter = Counter(item.semantic_type for item in columns)
        type_counts = tuple(
            SemanticTypeCount(semantic_type=semantic_type, count=type_counter[semantic_type])
            for semantic_type in SemanticType
            if type_counter[semantic_type]
        )
        missing_cells = sum(item.null_count for item in columns)
        cells = len(table) * len(table.columns)
        summary = DatasetSummary(
            row_count=len(table),
            column_count=len(table.columns),
            cell_count=cells,
            memory_bytes=int(table.memory_usage(index=True, deep=True).sum()),
            missing_cell_count=missing_cells,
            missing_percentage=_percentage(missing_cells, cells),
            duplicate_row_count=duplicate_count,
            duplicate_row_percentage=duplicate_percentage,
            semantic_type_counts=type_counts,
            empty_column_count=type_counter[SemanticType.EMPTY],
            constant_column_count=type_counter[SemanticType.CONSTANT],
            identifier_column_count=type_counter[SemanticType.IDENTIFIER],
        )
        return DatasetProfile(
            summary=summary,
            columns=tuple(columns),
            semantic_inference_version=semantic_profile.inference_version,
            configuration=self.config,
            run_metadata=ProfilingRunMetadata(
                source_kind=source_kind,
                total_rows=len(table),
                total_columns=len(table.columns),
                profiled_column_count=len(columns),
                failed_column_count=failed_count,
            ),
            warnings=tuple(dataset_warnings),
        )

    def _source_table(
        self, source: pd.DataFrame | IngestionResult
    ) -> tuple[pd.DataFrame, Literal["dataframe", "ingestion_result"]]:
        if isinstance(source, IngestionResult):
            return source.table, "ingestion_result"
        return source, "dataframe"

    def _validate_input(
        self,
        table: pd.DataFrame,
        source: pd.DataFrame | IngestionResult,
        semantic_profile: DatasetSemanticProfile,
    ) -> None:
        rows, columns = table.shape
        if isinstance(source, IngestionResult) and (
            source.row_count != rows or source.column_count != columns
        ):
            raise ProfilingError(
                ProfilingErrorCode.INPUT_SHAPE_MISMATCH,
                "The ingestion result dimensions do not match its table.",
            )
        if rows > self.config.max_rows:
            raise ProfilingError(
                ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED,
                f"The table exceeds the profiling row limit of {self.config.max_rows}.",
            )
        if columns > self.config.max_columns:
            raise ProfilingError(
                ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED,
                f"The table exceeds the profiling column limit of {self.config.max_columns}.",
            )
        if rows * columns > self.config.max_cells:
            raise ProfilingError(
                ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED,
                f"The table exceeds the profiling cell limit of {self.config.max_cells}.",
            )
        metadata = semantic_profile.run_metadata
        if (
            metadata.total_rows != rows
            or metadata.total_columns != columns
            or len(semantic_profile.columns) != columns
        ):
            raise ProfilingError(
                ProfilingErrorCode.SEMANTIC_PROFILE_MISMATCH,
                "The semantic profile dimensions do not match the table.",
            )

        for position, semantic in enumerate(semantic_profile.columns):
            series = table.iloc[:, position]
            null_count = int(series.isna().sum())
            name = _safe_column_name(table.columns[position], position)
            if (
                semantic.column_position != position
                or semantic.column_name != name
                or semantic.physical_dtype != str(series.dtype)
                or semantic.total_count != rows
                or semantic.null_count != null_count
                or semantic.non_null_count != rows - null_count
            ):
                raise ProfilingError(
                    ProfilingErrorCode.SEMANTIC_PROFILE_MISMATCH,
                    "A semantic column profile does not match the table.",
                    column_position=position,
                )
            if semantic.unique_count is not None:
                try:
                    unique_count = int(series.nunique(dropna=True))
                except (TypeError, ValueError):
                    unique_count = None
                if unique_count != semantic.unique_count:
                    raise ProfilingError(
                        ProfilingErrorCode.SEMANTIC_PROFILE_MISMATCH,
                        "A semantic column profile is stale for the table.",
                        column_position=position,
                    )

    def _statistics(
        self,
        series: pd.Series[Any],
        semantic: ColumnSemanticInference,
        warnings: list[ProfileWarning],
    ) -> ColumnStatistics | None:
        semantic_type = semantic.effective_type
        if semantic_type in {SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE}:
            return _numeric_statistics(series, self.config, semantic.column_position, warnings)
        if semantic_type in {SemanticType.CATEGORICAL, SemanticType.BOOLEAN}:
            return _categorical_statistics(series, self.config)
        if semantic_type is SemanticType.DATETIME:
            return _datetime_statistics(series, semantic.column_position, warnings)
        if semantic_type in {SemanticType.FREE_TEXT, SemanticType.IDENTIFIER}:
            return _text_statistics(series)
        if semantic_type is SemanticType.CONSTANT:
            if pd.api.types.is_numeric_dtype(series.dtype):
                return _numeric_statistics(series, self.config, semantic.column_position, warnings)
            if pd.api.types.is_datetime64_any_dtype(series.dtype):
                return _datetime_statistics(series, semantic.column_position, warnings)
            return _categorical_statistics(series, self.config)
        return None


def profile_dataset(
    source: pd.DataFrame | IngestionResult,
    semantic_profile: DatasetSemanticProfile,
    config: ProfilingConfig | None = None,
) -> DatasetProfile:
    """Convenience API for one exact deterministic profiling run."""

    return ProfilingService(config).profile(source, semantic_profile)


def _numeric_statistics(
    series: pd.Series[Any],
    config: ProfilingConfig,
    position: int,
    warnings: list[ProfileWarning],
) -> NumericStatistics:
    """Compute explicit finite-only estimators after scaling by max absolute value.

    Scaling is algebraically reversed for location, dispersion, and empirical quantiles. It
    prevents avoidable intermediate overflow without changing the selected estimators.
    """

    finite_values: list[int | float] = []
    positive_infinity_count = 0
    negative_infinity_count = 0
    non_numeric_count = 0
    for value in series[series.notna()].tolist():
        try:
            numeric = float(value)
        except (TypeError, ValueError, OverflowError):
            non_numeric_count += 1
            continue
        if math.isnan(numeric):
            non_numeric_count += 1
        elif math.isinf(numeric):
            if numeric > 0:
                positive_infinity_count += 1
            else:
                negative_infinity_count += 1
        elif isinstance(value, int) and not isinstance(value, bool):
            finite_values.append(int(value))
        else:
            finite_values.append(numeric)

    if non_numeric_count:
        warnings.append(
            ProfileWarning(
                code=ProfileWarningCode.NON_NUMERIC_VALUES_EXCLUDED,
                message="Non-numeric non-null values were excluded from numeric statistics.",
                column_position=position,
            )
        )
    if not finite_values:
        return NumericStatistics(
            finite_count=0,
            non_numeric_count=non_numeric_count,
            positive_infinity_count=positive_infinity_count,
            negative_infinity_count=negative_infinity_count,
            zero_count=0,
            positive_count=0,
            negative_count=0,
        )

    numeric_series = pd.Series(finite_values, dtype="float64")
    scale = max(abs(float(value)) for value in finite_values)
    scaled_series = numeric_series / scale if scale else numeric_series
    scaled_quantiles = scaled_series.quantile(
        [0.25, 0.5, 0.75], interpolation=config.quantile_interpolation
    )
    scaled_first_quartile = _finite_float(scaled_quantiles.loc[0.25])
    scaled_median = _finite_float(scaled_quantiles.loc[0.5])
    scaled_third_quartile = _finite_float(scaled_quantiles.loc[0.75])
    first_quartile = _rescale_statistic(scaled_first_quartile, scale)
    median = _rescale_statistic(scaled_median, scale)
    third_quartile = _rescale_statistic(scaled_third_quartile, scale)
    scaled_variance = _finite_float(scaled_series.var(ddof=config.standard_deviation_ddof))
    scaled_standard_deviation = _finite_float(
        scaled_series.std(ddof=config.standard_deviation_ddof)
    )
    variance = _rescale_variance(scaled_variance, scale)
    standard_deviation = _rescale_statistic(scaled_standard_deviation, scale)
    return NumericStatistics(
        finite_count=len(finite_values),
        non_numeric_count=non_numeric_count,
        positive_infinity_count=positive_infinity_count,
        negative_infinity_count=negative_infinity_count,
        zero_count=sum(value == 0 for value in finite_values),
        positive_count=sum(value > 0 for value in finite_values),
        negative_count=sum(value < 0 for value in finite_values),
        minimum=min(finite_values),
        maximum=max(finite_values),
        mean=_scaled_mean(finite_values, scale),
        median=median,
        standard_deviation=standard_deviation,
        variance=variance,
        first_quartile=first_quartile,
        third_quartile=third_quartile,
        interquartile_range=_scaled_difference(scaled_third_quartile, scaled_first_quartile, scale),
        skewness=_finite_float(scaled_series.skew()),
        kurtosis=_finite_float(scaled_series.kurt()),
    )


def _categorical_statistics(
    series: pd.Series[Any], config: ProfilingConfig
) -> CategoricalStatistics:
    counts: dict[tuple[str, Any], tuple[Any, int]] = {}
    for value in series[series.notna()].tolist():
        key = _category_identity(value)
        if key in counts:
            original, count = counts[key]
            counts[key] = (original, count + 1)
        else:
            counts[key] = (value, 1)
    if not counts:
        return CategoricalStatistics(category_count=0, other_value_count=0)

    ordered = sorted(counts.values(), key=lambda item: (-item[1], _value_sort_key(item[0])))
    total = sum(count for _, count in ordered)
    frequencies = tuple(
        ValueFrequency(
            value=_profile_value(value, config.max_value_display_length),
            count=count,
            percentage=_percentage(count, total),
        )
        for value, count in ordered[: config.top_values_limit]
    )
    entropy = -sum((count / total) * math.log2(count / total) for _, count in ordered)
    return CategoricalStatistics(
        category_count=len(ordered),
        mode=frequencies[0],
        top_values=frequencies,
        other_value_count=total - sum(item.count for item in frequencies),
        entropy_bits=entropy,
    )


def _datetime_statistics(
    series: pd.Series[Any], position: int, warnings: list[ProfileWarning]
) -> DatetimeStatistics:
    parsed: list[datetime] = []
    ambiguous_count = 0
    unparsed_count = 0
    for value in series[series.notna()].tolist():
        parsed_value, ambiguous = _parse_datetime(value)
        if ambiguous:
            ambiguous_count += 1
        elif parsed_value is None:
            unparsed_count += 1
        else:
            parsed.append(parsed_value)

    awareness = {value.tzinfo is not None and value.utcoffset() is not None for value in parsed}
    if not parsed:
        timezone_state: Literal["none", "naive", "aware", "mixed"] = "none"
    elif awareness == {False}:
        timezone_state = "naive"
    elif awareness == {True}:
        timezone_state = "aware"
    else:
        timezone_state = "mixed"

    earliest: str | None = None
    latest: str | None = None
    span_seconds: float | None = None
    comparable = parsed
    if timezone_state == "aware":
        comparable = [value.astimezone(UTC) for value in parsed]
    elif timezone_state == "mixed":
        warnings.append(
            ProfileWarning(
                code=ProfileWarningCode.MIXED_DATETIME_AWARENESS,
                message=(
                    "A date range was not computed across mixed timezone-aware and naive values."
                ),
                column_position=position,
            )
        )
        comparable = []
    if comparable:
        minimum = min(comparable)
        maximum = max(comparable)
        earliest = minimum.isoformat()
        latest = maximum.isoformat()
        span_seconds = (maximum - minimum).total_seconds()
    if ambiguous_count:
        warnings.append(
            ProfileWarning(
                code=ProfileWarningCode.AMBIGUOUS_DATETIME_VALUES_EXCLUDED,
                message="Ambiguous slash-formatted dates were excluded from the date range.",
                column_position=position,
            )
        )
    return DatetimeStatistics(
        parsed_count=len(parsed),
        unparsed_count=unparsed_count,
        ambiguous_count=ambiguous_count,
        timezone_state=timezone_state,
        earliest=earliest,
        latest=latest,
        span_seconds=span_seconds,
    )


def _text_statistics(series: pd.Series[Any]) -> TextStatistics:
    values = [str(value) for value in series[series.notna()].tolist()]
    if not values:
        return TextStatistics(empty_string_count=0, whitespace_only_count=0)
    lengths = pd.Series([len(value) for value in values], dtype="int64")
    return TextStatistics(
        minimum_length=int(lengths.min()),
        maximum_length=int(lengths.max()),
        average_length=float(lengths.mean()),
        median_length=float(lengths.median()),
        empty_string_count=sum(value == "" for value in values),
        whitespace_only_count=sum(value != "" and value.isspace() for value in values),
    )


def _parse_datetime(value: Any) -> tuple[datetime | None, bool]:
    if isinstance(value, datetime):
        return value, False
    if isinstance(value, date):
        return datetime.combine(value, datetime.min.time()), False
    if not isinstance(value, str):
        return None, False
    text = value.strip()
    if "/" in text:
        parsed = []
        for date_format in ("%m/%d/%Y", "%d/%m/%Y", "%Y/%m/%d"):
            try:
                parsed.append(datetime.strptime(text, date_format))
            except ValueError:
                pass
        unique = {item.date() for item in parsed}
        if len(unique) > 1:
            return None, True
        return (parsed[0], False) if parsed else (None, False)
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")), False
    except ValueError:
        try:
            return datetime.combine(date.fromisoformat(text), datetime.min.time()), False
        except ValueError:
            return None, False


def _profile_value(value: Any, max_length: int) -> ProfileValue:
    if isinstance(value, bool):
        return ProfileValue(kind=ProfileValueKind.BOOLEAN, value=value)
    if isinstance(value, Integral):
        return ProfileValue(kind=ProfileValueKind.INTEGER, value=int(value))
    if isinstance(value, Real):
        numeric = float(value)
        if math.isfinite(numeric):
            return ProfileValue(kind=ProfileValueKind.FLOAT, value=numeric)
        rendered = "Infinity" if numeric > 0 else "-Infinity"
        return ProfileValue(kind=ProfileValueKind.FLOAT, value=rendered)
    if isinstance(value, datetime):
        return ProfileValue(kind=ProfileValueKind.DATETIME, value=value.isoformat())
    if isinstance(value, date):
        return ProfileValue(kind=ProfileValueKind.DATE, value=value.isoformat())
    rendered = str(value)
    if len(rendered) <= max_length:
        return ProfileValue(kind=ProfileValueKind.STRING, value=rendered)
    return ProfileValue(
        kind=ProfileValueKind.STRING,
        value=rendered[:max_length],
        truncated=True,
        original_length=len(rendered),
        fingerprint=sha256(rendered.encode("utf-8", errors="surrogatepass")).hexdigest(),
    )


def _value_sort_key(value: Any) -> tuple[str, str]:
    kind, identity = _category_identity(value)
    return kind, str(identity)


def _category_identity(value: Any) -> tuple[str, Any]:
    if isinstance(value, bool):
        return ProfileValueKind.BOOLEAN.value, value
    if isinstance(value, Integral):
        return ProfileValueKind.INTEGER.value, int(value)
    if isinstance(value, Real):
        return ProfileValueKind.FLOAT.value, float(value).hex()
    if isinstance(value, datetime):
        return ProfileValueKind.DATETIME.value, value.isoformat()
    if isinstance(value, date):
        return ProfileValueKind.DATE.value, value.isoformat()
    if isinstance(value, str):
        return ProfileValueKind.STRING.value, value
    type_name = f"{type(value).__module__}.{type(value).__qualname__}"
    hash(value)
    return type_name, value


def _cardinality(
    series: pd.Series[Any],
    semantic: ColumnSemanticInference,
    statistics: ColumnStatistics | None,
) -> tuple[int | None, float | None]:
    if isinstance(statistics, CategoricalStatistics):
        denominator = semantic.non_null_count
        return (
            statistics.category_count,
            statistics.category_count / denominator if denominator else None,
        )
    if semantic.unique_count is None:
        return None, None
    denominator = semantic.non_null_count
    return semantic.unique_count, semantic.unique_count / denominator if denominator else None


def _duplicate_summary(
    table: pd.DataFrame, warnings: list[ProfileWarning]
) -> tuple[int | None, float | None]:
    if len(table.columns) == 0:
        count = max(len(table) - 1, 0)
        return count, _percentage(count, len(table))
    try:
        count = int(table.duplicated(keep="first").sum())
    except (TypeError, ValueError):
        warnings.append(
            ProfileWarning(
                code=ProfileWarningCode.DUPLICATE_COUNT_UNAVAILABLE,
                message="Duplicate rows could not be compared safely.",
            )
        )
        return None, None
    return count, _percentage(count, len(table))


def _percentage(numerator: int, denominator: int) -> float:
    return numerator / denominator * 100.0 if denominator else 0.0


def _finite_float(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if math.isfinite(number) else None


def _scaled_mean(values: list[int | float], scale: float) -> float | None:
    if not scale:
        return 0.0
    scaled_mean = math.fsum(float(value) / scale for value in values) / len(values)
    return _finite_float(scaled_mean * scale)


def _rescale_statistic(value: float | None, scale: float) -> float | None:
    if value is None:
        return None
    return _finite_float(value * scale)


def _rescale_variance(value: float | None, scale: float) -> float | None:
    if value is None:
        return None
    if value == 0.0:
        return 0.0
    return _finite_float(value * scale * scale)


def _scaled_difference(larger: float | None, smaller: float | None, scale: float) -> float | None:
    if larger is None or smaller is None:
        return None
    return _rescale_statistic(larger - smaller, scale)


def _safe_column_name(label: Any, position: int) -> str:
    try:
        return str(label)
    except Exception:
        return f"column_{position}"
