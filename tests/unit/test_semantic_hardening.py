from __future__ import annotations

from typing import Any
from uuid import UUID

import pandas as pd
import pytest
from pydantic import ValidationError

from haralens.semantic import (
    EvidenceCode,
    InferenceConfidence,
    InferenceWarningCode,
    SemanticInferenceConfig,
    SemanticInferenceEngine,
    SemanticType,
)


def infer(
    values: Any,
    *,
    name: str,
    dtype: str | None = None,
    config: SemanticInferenceConfig | None = None,
) -> Any:
    series = pd.Series(values, dtype=dtype, name=name)
    return SemanticInferenceEngine(config).infer_column(name, 0, series)


def evidence_codes(result: Any) -> tuple[EvidenceCode, ...]:
    return tuple(item.code for item in result.evidence)


@pytest.mark.parametrize(
    "name,values,expected",
    [
        ("customer_id", range(1000, 1100), SemanticType.IDENTIFIER),
        ("customer_number", range(1000, 1100), SemanticType.IDENTIFIER),
        ("account_number", range(1000, 1100), SemanticType.IDENTIFIER),
        ("invoice_no", range(1000, 1100), SemanticType.IDENTIFIER),
        ("order_code", [f"ORD-{index:04d}" for index in range(100)], SemanticType.IDENTIFIER),
        ("identity_score", range(100), SemanticType.NUMERIC_CONTINUOUS),
        ("number_of_children", range(100), SemanticType.NUMERIC_CONTINUOUS),
        ("account_balance", range(100), SemanticType.NUMERIC_CONTINUOUS),
        ("account_age", range(100), SemanticType.NUMERIC_CONTINUOUS),
        (
            "product_code",
            [f"PROD-{index:04d}" for index in range(100)],
            SemanticType.IDENTIFIER,
        ),
        ("postal_code", [f"ZIP-{index:04d}" for index in range(100)], SemanticType.UNKNOWN),
        ("phone_number", [f"555000{index:04d}" for index in range(100)], SemanticType.IDENTIFIER),
        ("transaction_number", range(1000, 1100), SemanticType.IDENTIFIER),
        ("reference", [f"REF-{index:04d}" for index in range(100)], SemanticType.IDENTIFIER),
        (
            "reference_number",
            [f"REF-{index:04d}" for index in range(100)],
            SemanticType.IDENTIFIER,
        ),
    ],
)
def test_identifier_business_name_matrix(name: str, values: Any, expected: SemanticType) -> None:
    assert infer(values, name=name).semantic_type is expected


@pytest.mark.parametrize("name", ["number", "no", "code", "key"])
def test_generic_identifier_tokens_do_not_decide_type(name: str) -> None:
    result = infer(range(1000, 1100), name=name)
    assert result.semantic_type is SemanticType.NUMERIC_CONTINUOUS
    assert EvidenceCode.NAME_HINT_IDENTIFIER not in evidence_codes(result)


def test_uniqueness_without_name_or_structure_never_creates_identifier() -> None:
    result = infer(range(50_000, 50_100), name="salary")
    assert result.semantic_type is SemanticType.NUMERIC_CONTINUOUS


def test_structured_values_without_identifier_context_remain_unknown() -> None:
    result = infer([f"ABC-{index:04d}" for index in range(100)], name="value")
    assert result.semantic_type is SemanticType.UNKNOWN
    assert EvidenceCode.STRUCTURED_CODE_PATTERN not in evidence_codes(result)


def test_repeated_structured_identifier_reduces_confidence() -> None:
    values = [f"PROD-{index:04d}" for index in range(90)] + [
        f"PROD-{index:04d}" for index in range(10)
    ]
    result = infer(values, name="product_code")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert result.confidence is InferenceConfidence.MEDIUM
    assert EvidenceCode.IDENTIFIER_CANDIDATE_UNIQUENESS in evidence_codes(result)
    assert InferenceWarningCode.DUPLICATE_IDENTIFIER_VALUES in {
        warning.code for warning in result.warnings
    }


def test_repeated_unstructured_identifier_has_low_confidence() -> None:
    values = list(range(90)) + list(range(10))
    result = infer(values, name="customer_id")
    assert result.semantic_type is SemanticType.IDENTIFIER
    assert result.confidence is InferenceConfidence.LOW
    assert InferenceWarningCode.DUPLICATE_IDENTIFIER_VALUES in {
        warning.code for warning in result.warnings
    }


def test_heavily_repeated_identifier_candidate_does_not_force_identifier() -> None:
    values = [f"PROD-{index:02d}" for index in range(10)] * 10
    assert infer(values, name="product_code").semantic_type is SemanticType.CATEGORICAL


def test_strong_identifier_name_without_uniqueness_does_not_force_identifier() -> None:
    values = ["A", "B"] * 50
    assert infer(values, name="customer_id").semantic_type is SemanticType.CATEGORICAL


def test_generic_reference_requires_value_structure() -> None:
    values = [f"arbitrary value {index}" for index in range(100)]
    assert infer(values, name="reference").semantic_type is SemanticType.UNKNOWN


@pytest.mark.parametrize(
    "name,values,dtype,expected",
    [
        ("is_active", [0, 1] * 20, None, SemanticType.BOOLEAN),
        ("has_defaulted", [0, 1] * 20, None, SemanticType.BOOLEAN),
        ("loan_status", ["0", "1"] * 20, "string", SemanticType.CATEGORICAL),
        ("segment", ["0", "1"] * 20, "string", SemanticType.CATEGORICAL),
        ("rating", [0, 1] * 20, None, SemanticType.NUMERIC_DISCRETE),
        ("binary_target", [0, 1] * 20, None, SemanticType.NUMERIC_DISCRETE),
        ("unknown_name", ["0", "1"] * 20, "string", SemanticType.CATEGORICAL),
    ],
)
def test_boolean_asymmetry_matrix(
    name: str, values: list[int] | list[str], dtype: str | None, expected: SemanticType
) -> None:
    result = infer(values, name=name, dtype=dtype)
    assert result.semantic_type is expected
    if expected is not SemanticType.BOOLEAN:
        assert result.alternative_candidates[0].semantic_type is SemanticType.BOOLEAN


def test_textual_zero_one_with_flag_hint_is_boolean() -> None:
    result = infer(["0", "1"] * 20, name="is_active", dtype="string")
    assert result.semantic_type is SemanticType.BOOLEAN
    assert EvidenceCode.BOOLEAN_NAME_HINT in evidence_codes(result)


@pytest.mark.parametrize(
    "distinct,rows,expected",
    [
        (20, 100, SemanticType.NUMERIC_DISCRETE),
        (21, 100, SemanticType.NUMERIC_CONTINUOUS),
        (20, 10_000, SemanticType.NUMERIC_DISCRETE),
        (500, 20_000, SemanticType.NUMERIC_CONTINUOUS),
        (2_000, 100_000, SemanticType.NUMERIC_CONTINUOUS),
    ],
)
def test_numeric_threshold_stages(distinct: int, rows: int, expected: SemanticType) -> None:
    values = [index % distinct for index in range(rows)]
    assert infer(values, name="feature").semantic_type is expected


@pytest.mark.parametrize(
    "distinct,rows,expected",
    [
        (20, 100, SemanticType.CATEGORICAL),
        (21, 100, SemanticType.UNKNOWN),
        (20, 10_000, SemanticType.CATEGORICAL),
        (500, 20_000, SemanticType.UNKNOWN),
        (2_000, 100_000, SemanticType.UNKNOWN),
    ],
)
def test_text_threshold_stages(distinct: int, rows: int, expected: SemanticType) -> None:
    values = [f"V{index % distinct}" for index in range(rows)]
    assert infer(values, name="feature").semantic_type is expected


def test_ratio_threshold_requires_supporting_name_context() -> None:
    values = [index % 500 for index in range(20_000)]
    measurement = infer(values, name="account_balance")
    category_codes = infer(values, name="risk_category")
    assert measurement.semantic_type is SemanticType.NUMERIC_CONTINUOUS
    assert category_codes.semantic_type is SemanticType.NUMERIC_DISCRETE
    assert EvidenceCode.NAME_HINT_CATEGORICAL in evidence_codes(category_codes)


def test_high_cardinality_string_ratio_requires_category_name_context() -> None:
    values = [f"V{index % 500}" for index in range(20_000)]
    assert infer(values, name="feature").semantic_type is SemanticType.UNKNOWN
    category = infer(values, name="category_label")
    assert category.semantic_type is SemanticType.CATEGORICAL
    assert EvidenceCode.NAME_HINT_CATEGORICAL in evidence_codes(category)


@pytest.mark.parametrize(
    "values",
    [
        [20240101, 20240102] * 10,
        ["2024-001", "2024-002"] * 10,
        ["2024-01", "2024-02"] * 10,
        ["product-2024-01-01-v1", "product-2024-01-02-v2"] * 10,
        ["version 2026-01-01", "version 2026-01-02"] * 10,
    ],
)
def test_datetime_lookalikes_remain_non_datetime(values: list[Any]) -> None:
    assert infer(values, name="feature").semantic_type is not SemanticType.DATETIME


def test_ambiguous_dates_remain_low_confidence_without_locale_choice() -> None:
    result = infer(["01/02/2026", "02/03/2026"] * 10, name="event_date")
    assert result.semantic_type is SemanticType.DATETIME
    assert result.confidence is InferenceConfidence.LOW
    assert result.warnings[0].code is InferenceWarningCode.AMBIGUOUS_DATE_ORDER


def test_timezone_syntax_is_preserved_without_inferred_timezone_metadata() -> None:
    values = [f"2026-01-{day:02d}T12:30:00+02:00" for day in range(1, 13)]
    result = infer(values, name="event_time")
    assert result.semantic_type is SemanticType.DATETIME
    assert "timezone" not in result.model_dump(mode="json")


def test_sampling_uses_physical_positions_and_includes_both_ends() -> None:
    config = SemanticInferenceConfig(max_inspection_values=10)
    values = [0.5, *range(1, 100), 100.5]
    first = pd.Series(values, index=range(101))
    relabeled = pd.Series(values, index=[f"row-{index}" for index in range(101)])
    engine = SemanticInferenceEngine(config)
    first_result = engine.infer_column("quantity", 0, first)
    relabeled_result = engine.infer_column("quantity", 0, relabeled)
    assert first_result == relabeled_result
    assert first_result.sampled is True
    assert first_result.sample_count == 10
    assert first_result.confidence is InferenceConfidence.MEDIUM
    assert EvidenceCode.DETERMINISTIC_SAMPLE in evidence_codes(first_result)
    assert EvidenceCode.NUMERIC_FRACTIONAL_VALUES in evidence_codes(first_result)


def test_sampled_iso_dates_cannot_retain_high_confidence() -> None:
    config = SemanticInferenceConfig(max_inspection_values=10)
    values = ["2026-01-01", "2026-01-02"] * 51
    result = infer(values, name="event_date", config=config)
    assert result.semantic_type is SemanticType.DATETIME
    assert result.sampled is True
    assert result.confidence is InferenceConfidence.MEDIUM


def test_identifier_candidate_threshold_must_not_exceed_strong_threshold() -> None:
    with pytest.raises(ValidationError):
        SemanticInferenceConfig(
            identifier_candidate_min_unique_ratio=0.99,
            identifier_min_unique_ratio=0.98,
        )


def test_high_confidence_is_reserved_for_strong_evidence() -> None:
    high_cases = [
        infer([None] * 12, name="empty"),
        infer([7] * 12, name="constant"),
        infer([True, False] * 6, name="flag"),
        infer(pd.date_range("2026-01-01", periods=12), name="event_date"),
        infer([str(UUID(int=index)) for index in range(1, 13)], name="opaque"),
        infer(["true", "false"] * 6, name="answer"),
        infer([f"2026-01-{day:02d}" for day in range(1, 13)], name="event_date"),
        infer([0, 1] * 6, name="is_active"),
        infer([1.1, 2.2, 3.3] * 4, name="measurement"),
        infer(["north", "south"] * 6, name="region", dtype="category"),
        infer(range(1000, 1012), name="customer_id"),
    ]
    assert all(result.confidence is InferenceConfidence.HIGH for result in high_cases)

    heuristic_cases = [
        infer(["yes", "no"] * 6, name="answer"),
        infer(["north", "south"] * 6, name="region"),
        infer(
            [f"Detailed note for case number {index}" for index in range(12)],
            name="notes",
        ),
    ]
    assert all(result.confidence is not InferenceConfidence.HIGH for result in heuristic_cases)
