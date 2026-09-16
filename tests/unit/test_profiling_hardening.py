"""Pre-freeze statistical, representation, resource, JSON, and privacy audit tests."""

from __future__ import annotations

import json
import math
import statistics
from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from haralens.profiling import (
    CategoricalStatistics,
    DatasetProfile,
    DatetimeStatistics,
    NumericStatistics,
    ProfileValueKind,
    ProfilingConfig,
    ProfilingError,
    ProfilingErrorCode,
    TextStatistics,
    profile_dataset,
)
from haralens.semantic import DatasetSemanticProfile, SemanticType, infer_semantic_types

RELATIVE_TOLERANCE = 1e-12
ABSOLUTE_TOLERANCE = 1e-12


def _force_type(
    semantic: DatasetSemanticProfile, position: int, semantic_type: SemanticType
) -> DatasetSemanticProfile:
    columns = list(semantic.columns)
    columns[position] = columns[position].model_copy(update={"user_confirmed_type": semantic_type})
    return semantic.model_copy(update={"columns": tuple(columns)})


def _numeric_profile(
    values: list[float], config: ProfilingConfig | None = None
) -> NumericStatistics:
    table = pd.DataFrame({"measurement": values})
    semantic = _force_type(infer_semantic_types(table), 0, SemanticType.NUMERIC_CONTINUOUS)
    statistics_result = profile_dataset(table, semantic, config).columns[0].statistics
    assert isinstance(statistics_result, NumericStatistics)
    return statistics_result


def _categorical_profile(
    values: list[Any], config: ProfilingConfig | None = None
) -> tuple[DatasetProfile, CategoricalStatistics]:
    table = pd.DataFrame({"category": pd.Series(values, dtype="object")})
    semantic = _force_type(infer_semantic_types(table), 0, SemanticType.CATEGORICAL)
    profile = profile_dataset(table, semantic, config)
    statistics_result = profile.columns[0].statistics
    assert isinstance(statistics_result, CategoricalStatistics)
    return profile, statistics_result


def _assert_close(actual: float | int | None, expected: float) -> None:
    assert actual is not None
    assert math.isclose(
        float(actual),
        expected,
        rel_tol=RELATIVE_TOLERANCE,
        abs_tol=ABSOLUTE_TOLERANCE,
    )


def _linear_quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = math.floor(index)
    upper = math.ceil(index)
    if lower == upper:
        return ordered[lower]
    fraction = index - lower
    scale = max(abs(ordered[lower]), abs(ordered[upper]))
    if not scale:
        return 0.0
    scaled_lower = ordered[lower] / scale
    scaled_upper = ordered[upper] / scale
    return (scaled_lower + (scaled_upper - scaled_lower) * fraction) * scale


def _bias_corrected_skewness(values: list[float]) -> float:
    count = len(values)
    mean = statistics.fmean(values)
    second_moment = math.fsum((value - mean) ** 2 for value in values) / count
    if second_moment == 0.0:
        return 0.0
    third_moment = math.fsum((value - mean) ** 3 for value in values) / count
    uncorrected = third_moment / second_moment**1.5
    return math.sqrt(count * (count - 1)) / (count - 2) * uncorrected


def _bias_corrected_excess_kurtosis(values: list[float]) -> float:
    count = len(values)
    mean = statistics.fmean(values)
    second_moment = math.fsum((value - mean) ** 2 for value in values) / count
    if second_moment == 0.0:
        return 0.0
    fourth_moment = math.fsum((value - mean) ** 4 for value in values) / count
    uncorrected_excess = fourth_moment / second_moment**2 - 3.0
    numerator = (count - 1) * ((count + 1) * uncorrected_excess + 6.0)
    return numerator / ((count - 2) * (count - 3))


@pytest.mark.parametrize(
    "values",
    [
        [1.0, 2.0, 3.0, 4.0, 5.0],
        [-9.0, -2.0, 0.0, 3.0, 11.0],
        [2.0, 2.0, 2.0, 5.0, 5.0, 9.0],
        [0.125, 0.5, 1.25, 2.75, 9.875],
    ],
)
def test_core_numeric_statistics_match_independent_standard_library_results(
    values: list[float],
) -> None:
    result = _numeric_profile(values)

    _assert_close(result.mean, statistics.fmean(values))
    _assert_close(result.median, statistics.median(values))
    _assert_close(result.variance, statistics.variance(values))
    _assert_close(result.standard_deviation, statistics.stdev(values))
    _assert_close(result.first_quartile, _linear_quantile(values, 0.25))
    _assert_close(result.third_quartile, _linear_quantile(values, 0.75))
    _assert_close(
        result.interquartile_range,
        _linear_quantile(values, 0.75) - _linear_quantile(values, 0.25),
    )


def test_population_variance_and_standard_deviation_match_standard_library() -> None:
    values = [-4.5, -1.25, 0.0, 2.75, 8.0]

    result = _numeric_profile(values, ProfilingConfig(standard_deviation_ddof=0))

    _assert_close(result.variance, statistics.pvariance(values))
    _assert_close(result.standard_deviation, statistics.pstdev(values))


@pytest.mark.parametrize(
    ("interpolation", "expected_q1", "expected_q3"),
    [
        ("linear", 12.5, 37.5),
        ("lower", 10.0, 30.0),
        ("higher", 20.0, 40.0),
        ("midpoint", 15.0, 35.0),
        ("nearest", 10.0, 40.0),
    ],
)
def test_each_configured_quantile_interpolation_is_locked(
    interpolation: str, expected_q1: float, expected_q3: float
) -> None:
    config = ProfilingConfig(quantile_interpolation=interpolation)  # type: ignore[arg-type]

    result = _numeric_profile([0.0, 10.0, 20.0, 30.0, 40.0, 50.0], config)

    _assert_close(result.first_quartile, expected_q1)
    _assert_close(result.third_quartile, expected_q3)
    _assert_close(result.interquartile_range, expected_q3 - expected_q1)


def test_skewness_and_kurtosis_match_explicit_bias_corrected_formulas() -> None:
    values = [1.0, 1.0, 2.0, 3.0, 8.0, 13.0]

    result = _numeric_profile(values)

    _assert_close(result.skewness, _bias_corrected_skewness(values))
    _assert_close(result.kurtosis, _bias_corrected_excess_kurtosis(values))


def test_moment_minimum_samples_and_constant_convention_are_locked() -> None:
    two = _numeric_profile([1.0, 3.0])
    three = _numeric_profile([1.0, 2.0, 4.0])
    four = _numeric_profile([1.0, 2.0, 4.0, 8.0])
    constant = _numeric_profile([2.0] * 5)

    assert two.skewness is None
    assert two.kurtosis is None
    assert three.skewness is not None
    assert three.kurtosis is None
    assert four.kurtosis is not None
    assert constant.skewness == 0.0
    assert constant.kurtosis == 0.0


def test_one_and_two_observation_variance_definitions() -> None:
    one = _numeric_profile([7.0])
    two = _numeric_profile([1.0, 3.0])
    one_population = _numeric_profile([7.0], ProfilingConfig(standard_deviation_ddof=0))

    assert one.variance is None
    assert one.standard_deviation is None
    assert one_population.variance == 0.0
    assert one_population.standard_deviation == 0.0
    assert two.variance == 2.0
    _assert_close(two.standard_deviation, math.sqrt(2.0))


def test_values_around_1e150_match_independent_results() -> None:
    values = [1.0e150, 1.1e150, 1.2e150, 1.3e150, 1.4e150]

    result = _numeric_profile(values)

    _assert_close(result.mean, statistics.fmean(values))
    _assert_close(result.variance, statistics.variance(values))
    _assert_close(result.standard_deviation, statistics.stdev(values))
    _assert_close(result.first_quartile, 1.1e150)
    _assert_close(result.third_quartile, 1.3e150)
    _assert_close(result.interquartile_range, 2.0e149)


def test_near_float_limit_opposite_sign_values_keep_finite_quantiles_and_stddev() -> None:
    values = [-1.0e308, -5.0e307, 5.0e307, 1.0e308]
    scaled = [-1.0, -0.5, 0.5, 1.0]

    result = _numeric_profile(values)

    assert result.mean == 0.0
    _assert_close(result.median, 0.0)
    _assert_close(result.first_quartile, -6.25e307)
    _assert_close(result.third_quartile, 6.25e307)
    _assert_close(result.interquartile_range, 1.25e308)
    _assert_close(result.standard_deviation, statistics.stdev(scaled) * 1.0e308)
    assert result.variance is None
    _assert_close(result.skewness, 0.0)


def test_near_float_limit_positive_values_avoid_naive_sum_overflow() -> None:
    values = [8.0e307, 9.0e307, 1.0e308]

    result = _numeric_profile(values)

    _assert_close(result.mean, 9.0e307)
    _assert_close(result.first_quartile, 8.5e307)
    _assert_close(result.third_quartile, 9.5e307)
    _assert_close(result.standard_deviation, 1.0e307)
    assert result.variance is None


def test_nan_and_infinities_are_excluded_from_all_finite_statistics() -> None:
    values = [1.0, 2.0, 3.0, float("nan"), float("inf"), float("-inf")]

    result = _numeric_profile(values)

    assert result.finite_count == 3
    assert result.positive_infinity_count == 1
    assert result.negative_infinity_count == 1
    assert result.mean == 2.0
    assert result.median == 2.0
    assert result.variance == 1.0
    assert result.first_quartile == 1.5
    assert result.third_quartile == 2.5
    _assert_close(result.skewness, 0.0)
    assert result.kurtosis is None


def test_long_categories_never_merge_and_truncated_displays_are_distinguishable() -> None:
    shared_prefix = "x" * 200
    first = shared_prefix + "A" + "a" * 5_000
    second = shared_prefix + "B" + "b" * 5_000
    profile, result = _categorical_profile(
        [first, second, first], ProfilingConfig(max_value_display_length=200)
    )

    assert profile.columns[0].unique_count == 2
    assert result.category_count == 2
    assert [item.count for item in result.top_values] == [2, 1]
    assert result.top_values[0].value.value == result.top_values[1].value.value
    fingerprints = {item.value.fingerprint for item in result.top_values}
    assert None not in fingerprints
    assert len(fingerprints) == 2
    assert all(len(fingerprint) == 64 for fingerprint in fingerprints if fingerprint)


@pytest.mark.parametrize(
    ("values", "expected_kinds"),
    [
        ([1, "1"], {ProfileValueKind.INTEGER, ProfileValueKind.STRING}),
        ([True, "True"], {ProfileValueKind.BOOLEAN, ProfileValueKind.STRING}),
        ([False, 0], {ProfileValueKind.BOOLEAN, ProfileValueKind.INTEGER}),
        (
            [date(2024, 1, 2), "2024-01-02"],
            {ProfileValueKind.DATE, ProfileValueKind.STRING},
        ),
    ],
)
def test_category_identity_preserves_physical_scalar_type(
    values: list[Any], expected_kinds: set[ProfileValueKind]
) -> None:
    profile, result = _categorical_profile(values)

    assert profile.columns[0].unique_count == 2
    assert result.category_count == 2
    assert {item.value.kind for item in result.top_values} == expected_kinds
    assert [item.count for item in result.top_values] == [1, 1]


def test_top_k_ties_use_canonical_identity_not_input_or_hash_order() -> None:
    config = ProfilingConfig(top_values_limit=2)
    _, first = _categorical_profile(["c", "a", "b", "c", "a", "b"], config)
    _, second = _categorical_profile(["b", "c", "a", "b", "c", "a"], config)

    first_values = [item.value.value for item in first.top_values]
    second_values = [item.value.value for item in second.top_values]
    assert first_values == second_values == ["a", "b"]
    assert first.other_value_count == second.other_value_count == 2
    assert first.category_count == second.category_count == 3


@pytest.mark.parametrize(
    ("table", "expected"),
    [
        (pd.DataFrame({"x": [1, 2, 3]}), 0),
        (pd.DataFrame({"x": [1, 1]}), 1),
        (pd.DataFrame({"x": [1, 1, 1]}), 2),
        (pd.DataFrame({"x": [None, None, 1]}), 1),
        (pd.DataFrame({"x": [1, 1], "y": ["a", "a"], "z": [True, True]}), 1),
        (pd.DataFrame(), 0),
        (pd.DataFrame({"x": [1]}), 0),
    ],
)
def test_duplicate_count_means_repeated_rows_after_first(
    table: pd.DataFrame, expected: int
) -> None:
    profile = profile_dataset(table, infer_semantic_types(table))

    assert profile.summary.duplicate_row_count == expected


@pytest.mark.parametrize("rows", [2, 3])
def test_row_limit_is_inclusive(rows: int) -> None:
    config = ProfilingConfig(max_rows=3)
    table = pd.DataFrame({"x": range(rows)})

    assert profile_dataset(table, infer_semantic_types(table), config).summary.row_count == rows


def test_row_limit_plus_one_is_rejected() -> None:
    table = pd.DataFrame({"x": range(4)})
    with pytest.raises(ProfilingError) as caught:
        profile_dataset(table, infer_semantic_types(table), ProfilingConfig(max_rows=3))
    assert caught.value.code is ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED


@pytest.mark.parametrize("columns", [2, 3])
def test_column_limit_is_inclusive(columns: int) -> None:
    table = pd.DataFrame({f"c{index}": [index] for index in range(columns)})
    config = ProfilingConfig(max_columns=3)

    assert (
        profile_dataset(table, infer_semantic_types(table), config).summary.column_count == columns
    )


def test_column_limit_plus_one_is_rejected() -> None:
    table = pd.DataFrame({f"c{index}": [index] for index in range(4)})
    with pytest.raises(ProfilingError) as caught:
        profile_dataset(table, infer_semantic_types(table), ProfilingConfig(max_columns=3))
    assert caught.value.code is ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED


@pytest.mark.parametrize(("rows", "columns"), [(1, 5), (2, 3)])
def test_cell_limit_is_inclusive(rows: int, columns: int) -> None:
    table = pd.DataFrame({f"c{index}": range(rows) for index in range(columns)})
    config = ProfilingConfig(max_rows=10, max_columns=10, max_cells=6)

    assert profile_dataset(table, infer_semantic_types(table), config).summary.cell_count <= 6


def test_cell_limit_plus_one_is_rejected() -> None:
    table = pd.DataFrame({f"c{index}": range(2) for index in range(4)})
    config = ProfilingConfig(max_rows=10, max_columns=10, max_cells=7)

    with pytest.raises(ProfilingError) as caught:
        profile_dataset(table, infer_semantic_types(table), config)
    assert caught.value.code is ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED


def test_arbitrary_precision_cell_limit_arithmetic_is_safe() -> None:
    table = pd.DataFrame({"x": [1]})
    config = ProfilingConfig(max_rows=10, max_columns=10, max_cells=10**100)

    assert profile_dataset(table, infer_semantic_types(table), config).summary.cell_count == 1


def test_representative_profile_round_trip_uses_strict_standard_json() -> None:
    long_a = "secret-prefix-" + "a" * 300
    long_b = "secret-prefix-" + "b" * 300
    table = pd.DataFrame(
        {
            "measurement": [1.0, 2.0, float("inf"), float("-inf"), float("nan"), 3.0],
            "single": [7.0, None, None, None, None, None],
            "category": pd.Series([1, "1", True, "True", long_a, long_b], dtype="object"),
            "aware_at": pd.to_datetime(
                [
                    "2024-01-01T00:00:00Z",
                    "2024-01-02T00:00:00Z",
                    None,
                    None,
                    None,
                    None,
                ]
            ),
            "ambiguous_at": ["01/02/2024", "03/04/2024"] * 3,
        }
    )
    semantic = infer_semantic_types(table)
    semantic = _force_type(semantic, 0, SemanticType.NUMERIC_CONTINUOUS)
    semantic = _force_type(semantic, 2, SemanticType.CATEGORICAL)
    profile = profile_dataset(table, semantic)

    payload = profile.model_dump_json()

    assert "NaN" not in payload
    assert "Infinity" not in payload
    assert "-Infinity" not in payload

    def reject_constant(value: str) -> Any:
        raise AssertionError(f"Non-standard JSON constant: {value}")

    parsed = json.loads(payload, parse_constant=reject_constant)
    json.dumps(parsed, allow_nan=False)
    assert DatasetProfile.model_validate_json(payload) == profile
    assert isinstance(profile.columns[0].statistics, NumericStatistics)
    assert isinstance(profile.columns[3].statistics, DatetimeStatistics)
    assert isinstance(profile.columns[4].statistics, DatetimeStatistics)


def test_profile_models_reject_non_finite_computed_fields() -> None:
    with pytest.raises(ValidationError):
        NumericStatistics(
            finite_count=1,
            non_numeric_count=0,
            positive_infinity_count=0,
            negative_infinity_count=0,
            zero_count=0,
            positive_count=1,
            negative_count=0,
            mean=float("nan"),
        )


def test_profiling_emits_no_sensitive_values_to_logs(caplog: pytest.LogCaptureFixture) -> None:
    secrets = {
        "TOP-CATEGORY-SECRET",
        "CUSTOMER-ID-SECRET-0001",
        "FREE-TEXT-SECRET-CONTENT",
        "2042-06-07T08:09:10",
        "CONSTANT-RAW-SECRET",
    }
    table = pd.DataFrame(
        {
            "region": ["TOP-CATEGORY-SECRET", "TOP-CATEGORY-SECRET", "other", "other"],
            "customer_id": [
                "CUSTOMER-ID-SECRET-0001",
                "CUSTOMER-ID-SECRET-0002",
                "CUSTOMER-ID-SECRET-0003",
                "CUSTOMER-ID-SECRET-0004",
            ],
            "notes": [f"FREE-TEXT-SECRET-CONTENT {index} " * 4 for index in range(4)],
            "event_at": [datetime(2042, 6, 7, 8, 9, 10, tzinfo=UTC)] * 4,
            "constant": ["CONSTANT-RAW-SECRET"] * 4,
        }
    )
    semantic = infer_semantic_types(table)
    caplog.clear()

    profile = profile_dataset(table, semantic)

    assert isinstance(profile.columns[2].statistics, TextStatistics)
    for secret in secrets:
        assert secret not in caplog.text
