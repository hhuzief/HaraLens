from __future__ import annotations

from datetime import date, datetime
from typing import Any
from uuid import UUID

import pandas as pd
import pytest
from pydantic import ValidationError

from haralens.ingestion import IngestionMetadata, IngestionResult, SourceType
from haralens.semantic import (
    EvidenceCode,
    InferenceConfidence,
    InferenceWarningCode,
    SemanticInferenceConfig,
    SemanticInferenceEngine,
    SemanticInferenceService,
    SemanticType,
    infer_semantic_types,
)


def infer(
    values: Any,
    *,
    name: str = "column",
    dtype: str | None = None,
    config: SemanticInferenceConfig | None = None,
) -> Any:
    series = pd.Series(values, dtype=dtype, name=name)
    return SemanticInferenceEngine(config).infer_column(name, 0, series)


def evidence_codes(result: Any) -> tuple[EvidenceCode, ...]:
    return tuple(item.code for item in result.evidence)


@pytest.mark.parametrize(
    "values,dtype",
    [([None, None], "string"), ([float("nan"), float("nan")], "float64")],
)
def test_all_null_columns_are_empty(values: list[Any], dtype: str) -> None:
    result = infer(values, dtype=dtype)
    assert result.semantic_type is SemanticType.EMPTY
    assert result.confidence is InferenceConfidence.HIGH
    assert result.non_null_count == 0
    assert result.unique_count == 0
    assert EvidenceCode.ALL_NULL in evidence_codes(result)


@pytest.mark.parametrize(
    "values,dtype",
    [([7, 7, None], "Int64"), (["ACTIVE", "ACTIVE", None], "string")],
)
def test_constant_columns_win_before_other_rules(values: list[Any], dtype: str) -> None:
    result = infer(values, dtype=dtype)
    assert result.semantic_type is SemanticType.CONSTANT
    assert result.unique_count == 1
    assert EvidenceCode.CONSTANT_VALUE in evidence_codes(result)
    assert "ACTIVE" not in result.model_dump_json()


@pytest.mark.parametrize(
    "values,dtype,name",
    [
        ([True, False, True] * 4, "bool", "enabled"),
        (["true", "false"] * 6, "string", "answer"),
        ([" YES ", "no"] * 6, "string", "answer"),
        (["Y", " n "] * 6, "object", "answer"),
        (["TrUe", " FALSE "] * 6, "object", "answer"),
        ([0, 1] * 6, "int64", "is_active"),
    ],
)
def test_supported_boolean_representations(values: list[Any], dtype: str, name: str) -> None:
    result = infer(values, dtype=dtype, name=name)
    assert result.semantic_type is SemanticType.BOOLEAN


def test_string_boolean_name_hint_is_recorded_as_supporting_evidence() -> None:
    result = infer(["yes", "no"] * 6, name="is_enabled")
    assert EvidenceCode.BOOLEAN_NAME_HINT in evidence_codes(result)


def test_two_arbitrary_categories_are_not_boolean() -> None:
    result = infer(["Male", "Female"] * 8, dtype="string", name="gender")
    assert result.semantic_type is SemanticType.CATEGORICAL


def test_binary_numeric_without_boolean_hint_remains_discrete_and_ambiguous() -> None:
    result = infer([0, 1] * 8, name="credit_history")
    assert result.semantic_type is SemanticType.NUMERIC_DISCRETE
    assert result.alternative_candidates[0].semantic_type is SemanticType.BOOLEAN
    assert result.warnings[0].code is InferenceWarningCode.BINARY_NUMERIC_AMBIGUITY


def test_uuid_values_are_identifiers_without_name_hint() -> None:
    values = [str(UUID(int=index)) for index in range(1, 13)]
    result = infer(values, dtype="string", name="opaque")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert result.confidence is InferenceConfidence.HIGH
    assert EvidenceCode.UUID_PATTERN in evidence_codes(result)


def test_repeated_uuid_values_do_not_claim_high_uniqueness() -> None:
    values = [str(UUID(int=1)), str(UUID(int=2))] * 6
    result = infer(values, dtype="string", name="opaque")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert result.confidence is InferenceConfidence.MEDIUM
    assert EvidenceCode.HIGH_UNIQUENESS not in evidence_codes(result)
    assert result.warnings[0].code is InferenceWarningCode.DUPLICATE_IDENTIFIER_VALUES


def test_sequential_integer_identifier_uses_name_and_structure() -> None:
    result = infer(range(1001, 1013), name="CustomerID")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert EvidenceCode.NAME_HINT_IDENTIFIER in evidence_codes(result)
    assert EvidenceCode.MONOTONIC_INTEGER_SEQUENCE in evidence_codes(result)
    assert result.alternative_candidates[0].semantic_type is SemanticType.NUMERIC_DISCRETE


def test_high_cardinality_customer_codes_are_identifiers() -> None:
    result = infer([f"CUST-{index:04d}" for index in range(20)], name="customer_code")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert EvidenceCode.STRUCTURED_CODE_PATTERN in evidence_codes(result)


def test_repeated_codes_do_not_become_identifiers() -> None:
    result = infer(["A-01", "B-02"] * 20, name="customer_code")
    assert result.semantic_type is SemanticType.CATEGORICAL


def test_unique_salary_values_do_not_become_identifiers() -> None:
    result = infer(range(50_000, 50_030), name="Salary")
    assert result.semantic_type is SemanticType.NUMERIC_CONTINUOUS


def test_id_substring_is_not_a_name_token() -> None:
    result = infer(range(30), name="identity_score")
    assert result.semantic_type is SemanticType.NUMERIC_CONTINUOUS
    assert EvidenceCode.NAME_HINT_IDENTIFIER not in evidence_codes(result)


def test_account_balance_measurement_is_not_identifier() -> None:
    result = infer(range(100, 130), name="account_balance")
    assert result.semantic_type is SemanticType.NUMERIC_CONTINUOUS


@pytest.mark.parametrize(
    "values,dtype",
    [
        (pd.date_range("2026-01-01", periods=12), None),
        ([date(2026, 1, day) for day in range(1, 13)], "object"),
        ([datetime(2026, 1, day, 12, 30) for day in range(1, 13)], "object"),
        ([f"2026-01-{day:02d}" for day in range(1, 13)], "string"),
        ([f"2026-01-{day:02d}T12:30:00Z" for day in range(1, 13)], "string"),
    ],
)
def test_supported_datetime_representations(values: Any, dtype: str | None) -> None:
    result = infer(values, dtype=dtype, name="event_date")
    assert result.semantic_type is SemanticType.DATETIME


def test_ambiguous_slash_dates_are_datetime_with_low_confidence_warning() -> None:
    result = infer(["01/02/2026", "02/03/2026"] * 6, name="event_date")
    assert result.semantic_type is SemanticType.DATETIME
    assert result.confidence is InferenceConfidence.LOW
    assert result.warnings[0].code is InferenceWarningCode.AMBIGUOUS_DATE_ORDER
    assert result.alternative_candidates[0].semantic_type is SemanticType.CATEGORICAL


def test_mostly_valid_dates_with_noise_use_configured_ratio() -> None:
    values = [f"2026-01-{day:02d}" for day in range(1, 10)] + ["not-a-date"]
    result = infer(values, name="event_date")
    assert result.semantic_type is SemanticType.DATETIME
    assert result.confidence is InferenceConfidence.MEDIUM
    assert result.warnings[0].code is InferenceWarningCode.PARTIAL_DATE_PARSE


def test_invalid_date_shaped_strings_do_not_parse() -> None:
    values = ["2026-99-99", "99/99/2026"] * 6
    assert infer(values, name="event_date").semantic_type is SemanticType.CATEGORICAL


def test_unambiguous_slash_dates_have_no_locale_warning() -> None:
    values = ["13/02/2026", "14/02/2026"] * 6
    result = infer(values, name="event_date")
    assert result.semantic_type is SemanticType.DATETIME
    assert all(
        warning.code is not InferenceWarningCode.AMBIGUOUS_DATE_ORDER for warning in result.warnings
    )


def test_datetime_parse_threshold_boundary_is_inclusive() -> None:
    values = [f"2026-01-{day:02d}" for day in range(1, 9)] + ["bad", "also bad"]
    config = SemanticInferenceConfig(datetime_min_parse_ratio=0.8)
    assert infer(values, name="event_date", config=config).semantic_type is SemanticType.DATETIME


@pytest.mark.parametrize(
    "values",
    [
        list(range(20240101, 20240113)),
        ["ordinary", "arbitrary", "words"] * 5,
    ],
)
def test_non_date_values_are_not_accidentally_parsed(values: list[Any]) -> None:
    assert infer(values, name="value").semantic_type is not SemanticType.DATETIME


@pytest.mark.parametrize(
    "values,name,expected",
    [
        ([1, 2, 1, 2] * 5, "rating", SemanticType.NUMERIC_DISCRETE),
        (range(100), "measurement", SemanticType.NUMERIC_CONTINUOUS),
        ([1.1, 2.2, 3.3, -4.4] * 3, "value", SemanticType.NUMERIC_CONTINUOUS),
        ([1.0, 2.0, 3.0] * 5, "quantity", SemanticType.NUMERIC_DISCRETE),
        ([-10, -5, 0, 5, 10] * 4, "bucket", SemanticType.NUMERIC_DISCRETE),
        ([0, 0, 0, 0, 1, 2] * 3, "count", SemanticType.NUMERIC_DISCRETE),
    ],
)
def test_numeric_continuous_and_discrete_rules(
    values: Any, name: str, expected: SemanticType
) -> None:
    assert infer(values, name=name).semantic_type is expected


def test_high_cardinality_integers_without_name_hint_are_continuous() -> None:
    assert infer(range(100), name="count").semantic_type is SemanticType.NUMERIC_CONTINUOUS


def test_complex_numeric_values_degrade_to_unknown() -> None:
    result = infer([1 + 2j, 3 + 4j], name="measurement")
    assert result.semantic_type is SemanticType.UNKNOWN
    assert EvidenceCode.UNSUPPORTED_PHYSICAL_DTYPE in evidence_codes(result)
    assert result.warnings[0].code is InferenceWarningCode.UNSUPPORTED_VALUES


def test_native_category_has_explicit_precedence() -> None:
    result = infer(["north", "south"] * 6, dtype="category", name="region")
    assert result.semantic_type is SemanticType.CATEGORICAL
    assert EvidenceCode.NATIVE_CATEGORICAL_DTYPE in evidence_codes(result)


@pytest.mark.parametrize(
    "values",
    [
        ["red", "blue", "green"] * 10,
        [f"label-{index % 10}" for index in range(100)],
    ],
)
def test_repeated_low_and_medium_cardinality_text_is_categorical(values: list[str]) -> None:
    assert infer(values, name="label").semantic_type is SemanticType.CATEGORICAL


def test_high_cardinality_short_labels_remain_unknown() -> None:
    result = infer([f"label{index}" for index in range(30)], name="label")
    assert result.semantic_type is SemanticType.UNKNOWN
    assert EvidenceCode.HIGH_CARDINALITY in evidence_codes(result)


def test_arrow_backed_strings_follow_the_same_text_rules() -> None:
    result = infer(["north", "south"] * 6, dtype="string[pyarrow]", name="region")
    assert result.semantic_type is SemanticType.CATEGORICAL
    assert result.physical_dtype.startswith("string")


def test_unique_short_names_remain_unknown() -> None:
    result = infer([f"Person {index}" for index in range(20)], name="person_name")
    assert result.semantic_type is SemanticType.UNKNOWN


@pytest.mark.parametrize("name", ["CustomerComment", "description", "review_text"])
def test_long_descriptive_text_is_free_text(name: str) -> None:
    values = [
        f"This is a detailed customer observation number {index}, with enough explanatory text."
        for index in range(12)
    ]
    result = infer(values, name=name)
    assert result.semantic_type is SemanticType.FREE_TEXT
    assert EvidenceCode.LONG_TEXT in evidence_codes(result)


def test_long_repeated_text_is_free_text_not_categorical() -> None:
    values = [
        "The customer reported a delayed delivery and requested a detailed investigation.",
        "The product documentation needs a clearer explanation for first-time operators.",
    ] * 10
    assert infer(values, name="notes").semantic_type is SemanticType.FREE_TEXT


def test_long_punctuated_text_without_whitespace_is_free_text() -> None:
    values = [f"token,token,token,token,token,token,token,token,{index}" for index in range(12)]
    result = infer(values, name="payload")
    assert result.semantic_type is SemanticType.FREE_TEXT
    assert EvidenceCode.TEXT_WHITESPACE not in evidence_codes(result)


def test_descriptive_name_can_support_shorter_structured_free_text() -> None:
    values = [f"Detailed note for case number {index}" for index in range(12)]
    result = infer(values, name="notes")
    assert result.semantic_type is SemanticType.FREE_TEXT
    assert EvidenceCode.NAME_HINT_FREE_TEXT in evidence_codes(result)
    assert EvidenceCode.LONG_TEXT not in evidence_codes(result)


def test_short_labels_remain_categorical_not_free_text() -> None:
    assert infer(["High", "Low"] * 10, name="label").semantic_type is SemanticType.CATEGORICAL


@pytest.mark.parametrize(
    "values,name,expected",
    [
        ([None] * 20 + ["A", "B"] * 5, "segment", SemanticType.CATEGORICAL),
        ([None] * 20 + [1.1, 2.2] * 5, "amount", SemanticType.NUMERIC_CONTINUOUS),
        ([None] * 20 + ["2026-01-01", "2026-01-02"] * 5, "date", SemanticType.DATETIME),
    ],
)
def test_nulls_do_not_create_categories(
    values: list[Any], name: str, expected: SemanticType
) -> None:
    result = infer(values, name=name)
    assert result.semantic_type is expected
    assert result.null_count == 20
    assert result.non_null_count == 10
    assert result.nullable is True


def test_numeric_identifier_conflict_exposes_alternative_and_warning() -> None:
    result = infer(range(20240001, 20240013), name="EmployeeNumber")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert result.alternative_candidates
    assert result.warnings[0].code is InferenceWarningCode.MULTIPLE_PLAUSIBLE_TYPES


def test_unique_dates_do_not_become_identifiers_from_uniqueness_alone() -> None:
    result = infer([f"2026-02-{day:02d}" for day in range(1, 13)], name="timestamp")
    assert result.semantic_type is SemanticType.DATETIME


@pytest.mark.parametrize(
    "field,value",
    [
        ("categorical_max_unique_count", 1),
        ("categorical_max_unique_ratio", -0.01),
        ("categorical_max_unique_ratio", 1.01),
        ("identifier_min_unique_ratio", -0.01),
        ("identifier_candidate_min_unique_ratio", -0.01),
        ("identifier_min_non_null", 1),
        ("numeric_discrete_max_unique_count", 1),
        ("free_text_min_average_length", 0.0),
        ("free_text_min_unique_ratio", 1.01),
        ("datetime_min_parse_ratio", 0.0),
        ("minimum_confident_non_null", 1),
        ("max_inspection_values", 9),
    ],
)
def test_configuration_rejects_invalid_thresholds(field: str, value: int | float) -> None:
    with pytest.raises(ValidationError):
        SemanticInferenceConfig(**{field: value})


def test_configuration_rejects_coercion_and_unknown_fields() -> None:
    with pytest.raises(ValidationError):
        SemanticInferenceConfig(max_inspection_values="100")
    with pytest.raises(ValidationError):
        SemanticInferenceConfig(unexplained_threshold=1)


def test_categorical_and_identifier_threshold_boundaries_are_inclusive() -> None:
    categorical_config = SemanticInferenceConfig(
        categorical_max_unique_count=2, categorical_max_unique_ratio=0.2
    )
    categorical = infer(["A"] * 5 + ["B"] * 5, config=categorical_config)
    assert categorical.semantic_type is SemanticType.CATEGORICAL

    identifier_values = list(range(98)) + [0, 1]
    identifier_config = SemanticInferenceConfig(identifier_min_unique_ratio=0.98)
    identifier = infer(identifier_values, name="record_id", config=identifier_config)
    assert identifier.semantic_type is SemanticType.IDENTIFIER


def test_small_samples_lower_confidence_and_emit_warning() -> None:
    result = infer([1.1, 2.2], name="amount")
    assert result.confidence is InferenceConfidence.MEDIUM
    assert result.warnings[0].code is InferenceWarningCode.INSUFFICIENT_OBSERVATIONS


def test_sampling_is_evenly_spaced_recorded_and_deterministic() -> None:
    config = SemanticInferenceConfig(max_inspection_values=10)
    series = pd.Series(range(101), name="measurement")
    engine = SemanticInferenceEngine(config)
    first = engine.infer_column("measurement", 0, series)
    second = engine.infer_column("measurement", 0, series)
    assert first == second
    assert first.sampled is True
    assert first.sample_count == 10
    assert EvidenceCode.DETERMINISTIC_SAMPLE in evidence_codes(first)


def test_non_hashable_values_degrade_to_unknown_without_raw_values() -> None:
    result = infer([["secret"], ["other"]], dtype="object")
    assert result.semantic_type is SemanticType.UNKNOWN
    assert result.unique_count is None
    assert result.warnings[0].code is InferenceWarningCode.UNSUPPORTED_VALUES
    assert "secret" not in result.model_dump_json()


def test_null_detection_failure_degrades_to_unknown(monkeypatch: pytest.MonkeyPatch) -> None:
    series = pd.Series(["secret", "other"])

    def fail_isna(_: pd.Series[Any]) -> pd.Series[bool]:
        raise ValueError("unsafe extension value")

    monkeypatch.setattr(pd.Series, "isna", fail_isna)
    result = SemanticInferenceEngine().infer_column("value", 0, series)
    assert result.semantic_type is SemanticType.UNKNOWN
    assert result.unique_count is None
    assert "secret" not in result.model_dump_json()


def test_mixed_scalar_values_degrade_to_unknown() -> None:
    result = infer([1, "two", 3], dtype="object")
    assert result.semantic_type is SemanticType.UNKNOWN
    assert EvidenceCode.MIXED_VALUE_TYPES in evidence_codes(result)


def test_override_extension_changes_effective_type_without_changing_inference() -> None:
    result = infer(["red", "blue"] * 6, name="color")
    overridden = result.model_copy(update={"user_confirmed_type": SemanticType.FREE_TEXT})
    assert overridden.semantic_type is SemanticType.CATEGORICAL
    assert overridden.effective_type is SemanticType.FREE_TEXT
    assert overridden.model_dump(mode="json")["user_confirmed_type"] == "free_text"


def test_dataset_service_preserves_input_order_and_does_not_mutate_dataframe() -> None:
    table = pd.DataFrame(
        {
            "customer_id": range(100, 112),
            "region": ["north", "south"] * 6,
            "amount": [1.5, 2.5, 3.5] * 4,
        }
    )
    original = table.copy(deep=True)
    profile = infer_semantic_types(table)
    pd.testing.assert_frame_equal(table, original)
    assert [item.column_name for item in profile.columns] == list(table.columns)
    assert [item.column_position for item in profile.columns] == [0, 1, 2]
    assert profile.run_metadata.total_rows == 12
    assert profile.run_metadata.total_columns == 3
    assert sum(item.count for item in profile.semantic_type_counts) == 3
    assert [(item.semantic_type, item.count) for item in profile.semantic_type_counts] == [
        (SemanticType.NUMERIC_CONTINUOUS, 1),
        (SemanticType.CATEGORICAL, 1),
        (SemanticType.IDENTIFIER, 1),
    ]


def test_duplicate_dataframe_labels_still_receive_one_ordered_result_each() -> None:
    table = pd.DataFrame([[1, "A"], [2, "B"]], columns=["value", "value"])
    profile = infer_semantic_types(table)
    assert len(profile.columns) == 2
    assert [item.column_position for item in profile.columns] == [0, 1]


def test_empty_dataframe_and_zero_row_columns_are_supported() -> None:
    assert infer_semantic_types(pd.DataFrame()).columns == ()
    profile = infer_semantic_types(pd.DataFrame(columns=["empty"]))
    assert profile.columns[0].semantic_type is SemanticType.EMPTY


def test_dataset_service_isolates_unexpected_column_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    service = SemanticInferenceService()
    original = service._engine.infer_column

    def fail_first(column_name: str, column_position: int, series: pd.Series[Any]) -> Any:
        if column_position == 0:
            raise ValueError("sensitive raw detail")
        return original(column_name, column_position, series)

    monkeypatch.setattr(service._engine, "infer_column", fail_first)
    profile = service.infer(pd.DataFrame({"broken": [1, 2], "healthy": [True, False]}))
    assert profile.columns[0].semantic_type is SemanticType.UNKNOWN
    assert profile.columns[1].semantic_type is SemanticType.BOOLEAN
    assert profile.run_metadata.failed_column_count == 1
    assert profile.warnings[0].code is InferenceWarningCode.COLUMN_INFERENCE_FAILED
    assert "sensitive" not in profile.model_dump_json()


def test_unprintable_dataframe_label_gets_safe_positional_name() -> None:
    class UnprintableLabel:
        def __str__(self) -> str:
            raise ValueError("unsafe label")

    table = pd.DataFrame([[1], [2]])
    table.columns = pd.Index([UnprintableLabel()])
    profile = infer_semantic_types(table)
    assert profile.columns[0].column_name == "column_0"


def test_ingestion_result_is_accepted_without_modifying_metadata() -> None:
    table = pd.DataFrame({"flag": [True, False] * 6})
    ingestion = IngestionResult(
        table=table,
        row_count=12,
        column_count=1,
        metadata=IngestionMetadata(
            source_type=SourceType.CSV,
            source_name="safe.csv",
            source_bytes=10,
            encoding="utf-8",
            duration_ms=1.0,
        ),
    )
    profile = SemanticInferenceService().infer(ingestion)
    assert profile.run_metadata.source_kind == "ingestion_result"
    assert profile.columns[0].semantic_type is SemanticType.BOOLEAN
    assert ingestion.table is table


def test_result_round_trip_is_serializable_and_versioned() -> None:
    profile = infer_semantic_types(pd.DataFrame({"flag": [True, False] * 6}))
    payload = profile.model_dump_json()
    assert profile.model_validate_json(payload) == profile
    assert profile.inference_version == "1.0.0"
    assert profile.columns[0].inference_version == "1.0.0"
