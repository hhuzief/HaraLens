from __future__ import annotations

from io import BytesIO

import pandas as pd
import pytest

from haralens.application import AnalysisResult, analyze_uploaded_dataset
from haralens.ingestion import IngestionError


def test_application_orchestration_has_installable_public_import() -> None:
    assert callable(analyze_uploaded_dataset)
    assert AnalysisResult.__module__ == "haralens.application.analysis"


def test_csv_runs_canonical_pipeline_without_raw_bytes_in_result() -> None:
    result = analyze_uploaded_dataset(b"id,value\na,1\nb,2\n", "customers.csv")
    assert result.source_name == "customers.csv"
    assert result.profile.summary.row_count == 2
    assert result.health.overall_score is not None
    assert result.recommendations.quality_run_reference == result.quality.metadata.run_reference
    assert not hasattr(result, "content")


def test_parquet_runs_canonical_pipeline() -> None:
    output = BytesIO()
    pd.DataFrame({"id": ["a", "b"], "value": [1, 2]}).to_parquet(output, index=False)
    result = analyze_uploaded_dataset(output.getvalue(), "customers.parquet")
    assert result.ingestion.metadata.source_type.value == "parquet"
    assert result.profile.summary.column_count == 2


def test_xlsx_runs_canonical_pipeline() -> None:
    output = BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        pd.DataFrame({"id": ["a", "b"], "value": [1, 2]}).to_excel(
            writer, sheet_name="Data", index=False
        )
    result = analyze_uploaded_dataset(output.getvalue(), "customers.xlsx", worksheet_name="Data")
    assert result.ingestion.metadata.source_type.value == "xlsx"
    assert result.ingestion.metadata.format_metadata is not None


def test_unsupported_and_malformed_uploads_are_typed_failures() -> None:
    with pytest.raises(ValueError, match="supports CSV"):
        analyze_uploaded_dataset(b"x", "customers.txt")
    with pytest.raises(IngestionError):
        analyze_uploaded_dataset(b"not,a,valid\n", "customers.csv")
