"""Phase 1D profiling contract, accuracy, determinism, and boundary tests."""

from datetime import UTC, date, datetime
from typing import Any

import pandas as pd
import pytest
from pydantic import ValidationError

from haralens.ingestion.models import (
    IngestionMetadata,
    IngestionResult,
    SourceType,
)
from haralens.profiling import (
    CategoricalStatistics,
    DatasetProfile,
    DatetimeStatistics,
    NumericStatistics,
    ProfileValueKind,
    ProfileWarningCode,
    ProfilingConfig,
    ProfilingError,
    ProfilingErrorCode,
    ProfilingService,
    TextStatistics,
    profile_dataset,
)
from haralens.semantic import SemanticType, infer_semantic_types


def _profile(table: pd.DataFrame, config: ProfilingConfig | None = None) -> DatasetProfile:
    return profile_dataset(table, infer_semantic_types(table), config)


def _ingestion_result(table: pd.DataFrame) -> IngestionResult:
    return IngestionResult(
        table=table,
        row_count=len(table),
        column_count=len(table.columns),
        metadata=IngestionMetadata(
            source_type=SourceType.CSV,
            source_name="input.csv",
            source_bytes=10,
            encoding="utf-8",
            duration_ms=1.0,
        ),
    )


def test_dataset_summary_and_column_order_are_exact() -> None:
    table = pd.DataFrame(
        {
            "amount": [1.0, 2.0, None, 4.0],
            "region": ["north", "south", "north", "south"],
        }
    )

    profile = _profile(table)

    assert profile.summary.row_count == 4
    assert profile.summary.column_count == 2
    assert profile.summary.cell_count == 8
    assert profile.summary.missing_cell_count == 1
    assert profile.summary.missing_percentage == 12.5
    assert profile.summary.duplicate_row_count == 0
    assert profile.summary.duplicate_row_percentage == 0.0
    assert profile.summary.memory_bytes == int(table.memory_usage(index=True, deep=True).sum())
    assert [column.column_name for column in profile.columns] == ["amount", "region"]
    assert profile.run_metadata.exact is True
    assert profile.run_metadata.profiled_column_count == 2


def test_duplicate_rows_count_only_repetitions_after_first() -> None:
    table = pd.DataFrame({"x": [1, 1, 1, 2], "y": [None, None, None, "a"]})

    summary = _profile(table).summary

    assert summary.duplicate_row_count == 2
    assert summary.duplicate_row_percentage == 50.0


@pytest.mark.parametrize(
    ("table", "expected_rows", "expected_columns", "expected_cells"),
    [
        (pd.DataFrame(), 0, 0, 0),
        (pd.DataFrame(columns=["a", "b"]), 0, 2, 0),
        (pd.DataFrame(index=range(3)), 3, 0, 0),
    ],
)
def test_empty_shapes_have_defined_zero_percentages(
    table: pd.DataFrame, expected_rows: int, expected_columns: int, expected_cells: int
) -> None:
    summary = _profile(table).summary

    assert (summary.row_count, summary.column_count, summary.cell_count) == (
        expected_rows,
        expected_columns,
        expected_cells,
    )
    assert summary.missing_percentage == 0.0
    if expected_rows == 3 and expected_columns == 0:
        assert summary.duplicate_row_count == 2
        assert summary.duplicate_row_percentage == pytest.approx(200 / 3)
    else:
        assert summary.duplicate_row_percentage == 0.0


def test_numeric_statistics_use_finite_values_and_report_non_finite_values() -> None:
    table = pd.DataFrame({"measurement": [-2.0, 0.0, 2.0, float("inf"), float("-inf"), None]})

    column = _profile(table).columns[0]
    statistics = column.statistics

    assert isinstance(statistics, NumericStatistics)
    assert statistics.finite_count == 3
    assert statistics.positive_infinity_count == 1
    assert statistics.negative_infinity_count == 1
    assert statistics.non_numeric_count == 0
    assert statistics.minimum == -2.0
    assert statistics.maximum == 2.0
    assert statistics.mean == 0.0
    assert statistics.median == 0.0
    assert statistics.variance == 4.0
    assert statistics.standard_deviation == 2.0
    assert statistics.first_quartile == -1.0
    assert statistics.third_quartile == 1.0
    assert statistics.interquartile_range == 2.0
    assert (statistics.negative_count, statistics.zero_count, statistics.positive_count) == (
        1,
        1,
        1,
    )


def test_numeric_population_variance_is_configurable() -> None:
    table = pd.DataFrame({"measurement": [1.0, 2.0, 3.0]})
    config = ProfilingConfig(standard_deviation_ddof=0)

    statistics = _profile(table, config).columns[0].statistics

    assert isinstance(statistics, NumericStatistics)
    assert statistics.variance == pytest.approx(2 / 3)
    assert statistics.standard_deviation == pytest.approx((2 / 3) ** 0.5)


def test_single_finite_numeric_value_has_no_sample_variance() -> None:
    table = pd.DataFrame({"constant": [5.0, None]})

    statistics = _profile(table).columns[0].statistics

    assert isinstance(statistics, NumericStatistics)
    assert statistics.mean == 5.0
    assert statistics.variance is None
    assert statistics.standard_deviation is None
    assert statistics.skewness is None
    assert statistics.kurtosis is None


def test_all_infinite_numeric_values_do_not_emit_non_finite_json_numbers() -> None:
    table = pd.DataFrame({"measurement": [float("inf"), float("-inf")]})

    profile = _profile(table)
    statistics = profile.columns[0].statistics

    assert isinstance(statistics, NumericStatistics)
    assert statistics.finite_count == 0
    assert statistics.minimum is None
    assert "Infinity" not in profile.model_dump_json()


def test_large_finite_numeric_values_have_a_stable_mean() -> None:
    table = pd.DataFrame({"measurement": [1e308, 1e308]})

    statistics = _profile(table).columns[0].statistics

    assert isinstance(statistics, NumericStatistics)
    assert statistics.mean == 1e308
    assert statistics.standard_deviation == 0.0
    assert statistics.variance == 0.0
    assert "Infinity" not in statistics.model_dump_json()


def test_categorical_frequencies_are_exact_bounded_and_stably_tied() -> None:
    table = pd.DataFrame({"region": ["b", "a", "c", "b", "a", None]})
    config = ProfilingConfig(top_values_limit=2)

    statistics = _profile(table, config).columns[0].statistics

    assert isinstance(statistics, CategoricalStatistics)
    assert [item.value.value for item in statistics.top_values] == ["a", "b"]
    assert [item.count for item in statistics.top_values] == [2, 2]
    assert statistics.mode == statistics.top_values[0]
    assert statistics.other_value_count == 1
    assert statistics.entropy_bits == pytest.approx(1.5219280948873621)


def test_frequency_values_preserve_scalar_type_and_bound_display_length() -> None:
    table = pd.DataFrame({"label": ["x" * 50, "x" * 50, "short"]})
    config = ProfilingConfig(max_value_display_length=16)

    statistics = _profile(table, config).columns[0].statistics

    assert isinstance(statistics, CategoricalStatistics)
    value = statistics.top_values[0].value
    assert value.kind is ProfileValueKind.STRING
    assert value.value == "x" * 16
    assert value.truncated is True
    assert value.original_length == 50


def test_boolean_profile_uses_exact_raw_frequency_values() -> None:
    table = pd.DataFrame({"enabled": pd.Series([True, False, True, None], dtype="boolean")})

    column = _profile(table).columns[0]
    statistics = column.statistics

    assert column.semantic_type is SemanticType.BOOLEAN
    assert isinstance(statistics, CategoricalStatistics)
    assert statistics.top_values[0].value.kind is ProfileValueKind.BOOLEAN
    assert statistics.top_values[0].value.value is True
    assert statistics.top_values[0].count == 2


def test_native_datetime_range_is_exact() -> None:
    table = pd.DataFrame(
        {"event_date": pd.to_datetime(["2024-01-01T00:00:00Z", "2024-01-03T12:00:00Z"])}
    )

    statistics = _profile(table).columns[0].statistics

    assert isinstance(statistics, DatetimeStatistics)
    assert statistics.parsed_count == 2
    assert statistics.timezone_state == "aware"
    assert statistics.earliest == "2024-01-01T00:00:00+00:00"
    assert statistics.latest == "2024-01-03T12:00:00+00:00"
    assert statistics.span_seconds == 216_000.0


def test_constant_native_datetime_uses_datetime_statistics() -> None:
    table = pd.DataFrame({"event_date": pd.to_datetime(["2024-01-01", "2024-01-01"])})

    column = _profile(table).columns[0]

    assert column.semantic_type is SemanticType.CONSTANT
    assert isinstance(column.statistics, DatetimeStatistics)
    assert column.statistics.span_seconds == 0.0


def test_partially_parseable_datetime_counts_unparsed_values() -> None:
    values = [f"2024-01-{day:02d}" for day in range(1, 10)] + ["not-a-date"]
    table = pd.DataFrame({"event_date": values})

    statistics = _profile(table).columns[0].statistics

    assert isinstance(statistics, DatetimeStatistics)
    assert statistics.parsed_count == 9
    assert statistics.unparsed_count == 1
    assert statistics.ambiguous_count == 0


def test_ambiguous_slash_dates_are_counted_without_guessing_order() -> None:
    table = pd.DataFrame({"event_date": ["01/02/2024", "03/04/2024", "05/06/2024"]})

    column = _profile(table).columns[0]
    statistics = column.statistics

    assert column.semantic_type is SemanticType.DATETIME
    assert isinstance(statistics, DatetimeStatistics)
    assert statistics.parsed_count == 0
    assert statistics.ambiguous_count == 3
    assert statistics.unparsed_count == 0
    assert statistics.earliest is None
    assert column.warnings[0].code is ProfileWarningCode.AMBIGUOUS_DATETIME_VALUES_EXCLUDED


def test_mixed_timezone_awareness_withholds_a_misleading_range() -> None:
    table = pd.DataFrame(
        {
            "event_date": [
                datetime(2024, 1, 1),
                datetime(2024, 1, 2, tzinfo=UTC),
                datetime(2024, 1, 3),
            ]
        }
    )

    semantic = infer_semantic_types(table)
    column_semantic = semantic.columns[0].model_copy(
        update={"semantic_type": SemanticType.DATETIME}
    )
    semantic = semantic.model_copy(update={"columns": (column_semantic,)})
    column = profile_dataset(table, semantic).columns[0]
    statistics = column.statistics

    assert isinstance(statistics, DatetimeStatistics)
    assert statistics.timezone_state == "mixed"
    assert statistics.earliest is None
    assert column.warnings[0].code is ProfileWarningCode.MIXED_DATETIME_AWARENESS


def test_free_text_and_identifier_profiles_do_not_retain_raw_values() -> None:
    table = pd.DataFrame(
        {
            "customer_id": ["C-1001", "C-1002", "C-1003", "C-1004"],
            "notes": [
                "A sufficiently long customer note with spaces and useful descriptive text A.",
                "A sufficiently long customer note with spaces and useful descriptive text B.",
                "A sufficiently long customer note with spaces and useful descriptive text C.",
                "A sufficiently long customer note with spaces and useful descriptive text D.",
            ],
        }
    )

    profile = _profile(table)

    assert profile.columns[0].semantic_type is SemanticType.IDENTIFIER
    assert isinstance(profile.columns[0].statistics, TextStatistics)
    assert profile.columns[1].semantic_type is SemanticType.FREE_TEXT
    assert isinstance(profile.columns[1].statistics, TextStatistics)
    serialized = profile.model_dump_json()
    assert "C-1001" not in serialized
    assert "sufficiently long customer note" not in serialized


def test_text_lengths_include_empty_and_whitespace_only_strings() -> None:
    table = pd.DataFrame({"notes": ["", "  ", "a useful sentence with several words " * 3]})
    semantic = infer_semantic_types(table)
    forced = semantic.columns[0].model_copy(update={"semantic_type": SemanticType.FREE_TEXT})
    semantic = semantic.model_copy(update={"columns": (forced,)})

    statistics = profile_dataset(table, semantic).columns[0].statistics

    assert isinstance(statistics, TextStatistics)
    assert statistics.minimum_length == 0
    assert statistics.empty_string_count == 1
    assert statistics.whitespace_only_count == 1


def test_empty_overridden_text_and_category_profiles_are_defined() -> None:
    table = pd.DataFrame({"empty": [None, None]})
    semantic = infer_semantic_types(table)

    text_semantic = semantic.columns[0].model_copy(
        update={"user_confirmed_type": SemanticType.FREE_TEXT}
    )
    text_profile = profile_dataset(table, semantic.model_copy(update={"columns": (text_semantic,)}))
    category_semantic = semantic.columns[0].model_copy(
        update={"user_confirmed_type": SemanticType.CATEGORICAL}
    )
    category_profile = profile_dataset(
        table, semantic.model_copy(update={"columns": (category_semantic,)})
    )

    assert isinstance(text_profile.columns[0].statistics, TextStatistics)
    assert text_profile.columns[0].statistics.minimum_length is None
    assert isinstance(category_profile.columns[0].statistics, CategoricalStatistics)
    assert category_profile.columns[0].statistics.mode is None


def test_forced_numeric_profile_counts_non_numeric_values_safely() -> None:
    table = pd.DataFrame({"measurement": ["1", "bad", "3"]})
    semantic = infer_semantic_types(table)
    forced = semantic.columns[0].model_copy(
        update={"user_confirmed_type": SemanticType.NUMERIC_CONTINUOUS}
    )

    column = profile_dataset(table, semantic.model_copy(update={"columns": (forced,)})).columns[0]

    assert isinstance(column.statistics, NumericStatistics)
    assert column.statistics.finite_count == 2
    assert column.statistics.non_numeric_count == 1
    assert column.warnings[0].code is ProfileWarningCode.NON_NUMERIC_VALUES_EXCLUDED


def test_categorical_profile_value_types_are_serializable() -> None:
    table = pd.DataFrame(
        {
            "mixed": [
                1,
                1.5,
                datetime(2024, 1, 1, 12),
                date(2024, 1, 2),
            ]
        }
    )
    semantic = infer_semantic_types(table)
    forced = semantic.columns[0].model_copy(
        update={"user_confirmed_type": SemanticType.CATEGORICAL}
    )

    statistics = (
        profile_dataset(table, semantic.model_copy(update={"columns": (forced,)}))
        .columns[0]
        .statistics
    )

    assert isinstance(statistics, CategoricalStatistics)
    assert {item.value.kind for item in statistics.top_values} == {
        ProfileValueKind.INTEGER,
        ProfileValueKind.FLOAT,
        ProfileValueKind.DATETIME,
        ProfileValueKind.DATE,
    }


def test_effective_user_override_drives_profile_type_and_distribution() -> None:
    table = pd.DataFrame({"code": [1, 2, 3, 4]})
    semantic = infer_semantic_types(table)
    overridden = semantic.columns[0].model_copy(
        update={"user_confirmed_type": SemanticType.IDENTIFIER}
    )
    semantic = semantic.model_copy(update={"columns": (overridden,)})

    profile = profile_dataset(table, semantic)

    assert profile.columns[0].inferred_semantic_type is SemanticType.NUMERIC_DISCRETE
    assert profile.columns[0].semantic_type is SemanticType.IDENTIFIER
    assert isinstance(profile.columns[0].statistics, TextStatistics)
    assert profile.summary.identifier_column_count == 1


def test_empty_column_has_no_specialized_statistics() -> None:
    table = pd.DataFrame({"empty": [None, None]})

    profile = _profile(table)

    assert profile.columns[0].semantic_type is SemanticType.EMPTY
    assert profile.columns[0].statistics is None
    assert profile.summary.empty_column_count == 1


def test_constant_columns_are_counted_and_profiled_by_physical_kind() -> None:
    table = pd.DataFrame({"constant": [7, 7, 7]})

    profile = _profile(table)

    assert profile.summary.constant_column_count == 1
    assert isinstance(profile.columns[0].statistics, NumericStatistics)


def test_profile_is_json_round_trip_serializable_and_frozen() -> None:
    table = pd.DataFrame({"region": ["north", "south", "north"]})
    profile = _profile(table)

    restored = DatasetProfile.model_validate_json(profile.model_dump_json())

    assert restored == profile
    with pytest.raises(ValidationError):
        profile.summary.row_count = 99  # type: ignore[misc]


def test_same_input_produces_identical_profile() -> None:
    table = pd.DataFrame({"value": [3.0, 1.0, 2.0], "category": ["b", "a", "b"]})
    semantic = infer_semantic_types(table)

    first = profile_dataset(table, semantic)
    second = profile_dataset(table, semantic)

    assert first.model_dump_json() == second.model_dump_json()


def test_profiling_does_not_mutate_table() -> None:
    table = pd.DataFrame({"value": [1.0, None, 3.0]})
    before = table.copy(deep=True)

    _profile(table)

    pd.testing.assert_frame_equal(table, before)


def test_ingestion_result_source_kind_and_shape_are_verified() -> None:
    table = pd.DataFrame({"value": [1, 2]})
    result = _ingestion_result(table)

    profile = profile_dataset(result, infer_semantic_types(result))

    assert profile.run_metadata.source_kind == "ingestion_result"

    inconsistent = IngestionResult(
        table=table,
        row_count=99,
        column_count=1,
        metadata=result.metadata,
    )
    with pytest.raises(ProfilingError) as caught:
        profile_dataset(inconsistent, infer_semantic_types(table))
    assert caught.value.code is ProfilingErrorCode.INPUT_SHAPE_MISMATCH


@pytest.mark.parametrize(
    ("config", "table"),
    [
        (ProfilingConfig(max_rows=1), pd.DataFrame({"x": [1, 2]})),
        (ProfilingConfig(max_columns=1), pd.DataFrame({"x": [1], "y": [2]})),
        (ProfilingConfig(max_cells=2), pd.DataFrame({"x": [1, 2], "y": [3, 4]})),
    ],
)
def test_resource_limits_fail_explicitly(config: ProfilingConfig, table: pd.DataFrame) -> None:
    with pytest.raises(ProfilingError) as caught:
        profile_dataset(table, infer_semantic_types(table), config)

    assert caught.value.code is ProfilingErrorCode.RESOURCE_LIMIT_EXCEEDED
    assert "limit" in str(caught.value)


def test_semantic_shape_name_dtype_and_staleness_mismatches_fail() -> None:
    original = pd.DataFrame({"value": [1, 2, 3]})
    semantic = infer_semantic_types(original)

    cases = [
        pd.DataFrame({"value": [1, 2]}),
        pd.DataFrame({"renamed": [1, 2, 3]}),
        pd.DataFrame({"value": [1.0, 2.0, 3.0]}),
        pd.DataFrame({"value": [1, 1, 3]}),
    ]
    for table in cases:
        with pytest.raises(ProfilingError) as caught:
            profile_dataset(table, semantic)
        assert caught.value.code is ProfilingErrorCode.SEMANTIC_PROFILE_MISMATCH


def test_duplicate_labels_are_profiled_by_position() -> None:
    table = pd.DataFrame([[1, "a"], [2, "b"]], columns=["same", "same"])

    profile = _profile(table)

    assert [column.column_position for column in profile.columns] == [0, 1]
    assert [column.physical_dtype for column in profile.columns] == ["int64", "str"]


def test_pathological_column_duplicate_comparison_degrades_safely() -> None:
    table = pd.DataFrame({"nested": [[1], [1]]})

    profile = _profile(table)

    if profile.summary.duplicate_row_count is None:
        assert profile.warnings[0].code is ProfileWarningCode.DUPLICATE_COUNT_UNAVAILABLE
    else:
        assert profile.summary.duplicate_row_count == 1


def test_duplicate_comparison_failure_returns_typed_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = pd.DataFrame({"value": [1, 2]})

    def fail_duplicate(*args: Any, **kwargs: Any) -> Any:
        raise TypeError("unsafe value")

    monkeypatch.setattr(pd.DataFrame, "duplicated", fail_duplicate)

    profile = _profile(table)

    assert profile.summary.duplicate_row_count is None
    assert profile.summary.duplicate_row_percentage is None
    assert profile.warnings[0].code is ProfileWarningCode.DUPLICATE_COUNT_UNAVAILABLE
    assert "unsafe value" not in profile.model_dump_json()


def test_column_statistics_failure_is_isolated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = pd.DataFrame({"first": [1.0, 2.0], "second": [3.0, 4.0]})
    service = ProfilingService()
    original = service._statistics
    calls = 0

    def fail_once(*args: Any, **kwargs: Any) -> Any:
        nonlocal calls
        calls += 1
        if calls == 1:
            raise RuntimeError("raw details must not escape")
        return original(*args, **kwargs)

    monkeypatch.setattr(service, "_statistics", fail_once)

    profile = service.profile(table, infer_semantic_types(table))

    assert profile.columns[0].statistics is None
    assert profile.columns[1].statistics is not None
    assert profile.run_metadata.failed_column_count == 1
    assert "raw details" not in profile.model_dump_json()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"top_values_limit": 0},
        {"max_value_display_length": 15},
        {"max_rows": 0},
        {"standard_deviation_ddof": 2},
        {"unexpected": True},
    ],
)
def test_profiling_config_is_strict(kwargs: dict[str, Any]) -> None:
    with pytest.raises(ValidationError):
        ProfilingConfig(**kwargs)  # type: ignore[arg-type]


def test_golden_business_profile() -> None:
    table = pd.DataFrame(
        {
            "amount": [10.0, 20.0, 30.0, None],
            "region": ["north", "south", "north", "south"],
            "closed_on": [date(2024, 1, 1), date(2024, 1, 2), date(2024, 1, 3), None],
        }
    )

    profile = _profile(table)

    assert profile.model_dump(mode="json", exclude={"configuration"}) == {
        "summary": {
            "row_count": 4,
            "column_count": 3,
            "cell_count": 12,
            "memory_bytes": int(table.memory_usage(index=True, deep=True).sum()),
            "missing_cell_count": 2,
            "missing_percentage": pytest.approx(16.666666666666664),
            "duplicate_row_count": 0,
            "duplicate_row_percentage": 0.0,
            "semantic_type_counts": [
                {"semantic_type": "numeric_continuous", "count": 1},
                {"semantic_type": "categorical", "count": 1},
                {"semantic_type": "datetime", "count": 1},
            ],
            "empty_column_count": 0,
            "constant_column_count": 0,
            "identifier_column_count": 0,
        },
        "columns": profile.model_dump(mode="json")["columns"],
        "profile_version": "1.0.0",
        "semantic_inference_version": "1.0.0",
        "run_metadata": {
            "source_kind": "dataframe",
            "exact": True,
            "total_rows": 4,
            "total_columns": 3,
            "profiled_column_count": 3,
            "failed_column_count": 0,
        },
        "warnings": [],
    }
