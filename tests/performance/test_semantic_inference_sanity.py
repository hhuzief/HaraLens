"""Representative bounded-size semantic inference checks without flaky timing assertions."""

import pandas as pd

from haralens.semantic import EvidenceCode, SemanticType, infer_semantic_types


def test_semantic_inference_on_100k_numeric_column() -> None:
    table = pd.DataFrame({"measurement": range(100_000)})
    result = infer_semantic_types(table).columns[0]
    assert result.semantic_type is SemanticType.NUMERIC_CONTINUOUS
    assert result.non_null_count == 100_000
    assert result.sampled is True
    assert result.sample_count == 10_000


def test_semantic_inference_on_100k_high_cardinality_strings() -> None:
    table = pd.DataFrame({"feature": [f"VALUE-{index:06d}" for index in range(100_000)]})
    result = infer_semantic_types(table).columns[0]
    assert result.semantic_type is SemanticType.UNKNOWN
    assert result.unique_count == 100_000
    assert EvidenceCode.DETERMINISTIC_SAMPLE in {item.code for item in result.evidence}


def test_semantic_inference_on_representative_mixed_dataframe() -> None:
    rows = 100_000
    table = pd.DataFrame(
        {
            "customer_id": range(rows),
            "amount": [float(index % 10_000) / 10 for index in range(rows)],
            "region": [f"region-{index % 12}" for index in range(rows)],
            "is_active": [index % 2 for index in range(rows)],
        }
    )
    profile = infer_semantic_types(table)
    assert [column.semantic_type for column in profile.columns] == [
        SemanticType.IDENTIFIER,
        SemanticType.NUMERIC_CONTINUOUS,
        SemanticType.CATEGORICAL,
        SemanticType.BOOLEAN,
    ]
    assert profile.run_metadata.sampled_column_count == 4
