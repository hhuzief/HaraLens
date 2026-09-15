import json

import pandas as pd
import pytest

from haralens.common.logging import configure_logging
from haralens.ingestion.csv import CsvIngestionAdapter
from haralens.ingestion.errors import (
    ColumnLimitExceededError,
    DuplicateColumnsError,
    EmptySourceError,
    IngestionConsistencyError,
    IngestionErrorCode,
    InvalidColumnNamesError,
    InvalidEncodingError,
    MalformedSourceError,
    NoDataRowsError,
    RowLimitExceededError,
    SourceTooLargeError,
    UnsupportedSourceError,
)
from haralens.ingestion.models import IngestionRequest, ResourceLimits, SourceType

DEFAULT_LIMITS = ResourceLimits(max_source_bytes=10_000, max_rows=100, max_columns=20)


def ingest(
    content: bytes,
    *,
    source_name: str = "data.csv",
    limits: ResourceLimits = DEFAULT_LIMITS,
):
    return CsvIngestionAdapter().ingest(
        IngestionRequest(content=content, source_name=source_name, limits=limits)
    )


def test_valid_utf8_csv_returns_table_and_metadata() -> None:
    result = ingest("city,value\nReykjavík,4\nAkureyri,7\n".encode())

    assert result.row_count == 2
    assert result.column_count == 2
    assert result.table.to_dict(orient="records") == [
        {"city": "Reykjavík", "value": 4},
        {"city": "Akureyri", "value": 7},
    ]
    assert result.metadata.source_type is SourceType.CSV
    assert result.metadata.source_name == "data.csv"
    assert result.metadata.encoding == "utf-8"
    assert result.metadata.source_bytes == len("city,value\nReykjavík,4\nAkureyri,7\n".encode())
    assert result.metadata.ingested_at.tzinfo is not None
    assert result.metadata.duration_ms >= 0


def test_utf8_bom_is_handled_without_changing_header() -> None:
    result = ingest(b"\xef\xbb\xbf" + "naïve,value\nA,1\n".encode())
    assert list(result.table.columns) == ["naïve", "value"]
    assert result.metadata.encoding == "utf-8-sig"


@pytest.mark.parametrize(
    ("content", "message"),
    [(b"", "zero bytes"), (b"\n\r\n", "no usable rows")],
)
def test_empty_sources_have_controlled_failures(content: bytes, message: str) -> None:
    with pytest.raises(EmptySourceError, match=message) as raised:
        ingest(content)
    assert raised.value.code is IngestionErrorCode.EMPTY_SOURCE


def test_quoted_empty_values_are_data_not_blank_physical_lines() -> None:
    result = ingest(b'a,b\n"",\n')
    assert result.row_count == 1
    assert result.table.iloc[0].isna().all()


def test_header_only_csv_is_distinct_from_empty_source() -> None:
    with pytest.raises(NoDataRowsError, match="header but no data rows") as raised:
        ingest(b"name,value\n")
    assert raised.value.code is IngestionErrorCode.NO_DATA_ROWS


def test_invalid_encoding_is_rejected_as_utf8_policy_failure() -> None:
    with pytest.raises(InvalidEncodingError, match="UTF-8") as raised:
        ingest(b"name\n\xff\n")
    assert raised.value.code is IngestionErrorCode.INVALID_ENCODING
    assert raised.value.__cause__ is not None


@pytest.mark.parametrize(
    "content",
    [
        b'name,value\n"broken,1\n',
        b"name,value\nA,1,extra\n",
        b"name,value\nA\n",
    ],
)
def test_malformed_csv_is_rejected_without_skipping_rows(content: bytes) -> None:
    with pytest.raises(MalformedSourceError) as raised:
        ingest(content)
    assert raised.value.code is IngestionErrorCode.MALFORMED_SOURCE


def test_malformed_header_quote_is_rejected() -> None:
    with pytest.raises(MalformedSourceError, match="quoting and rows"):
        ingest(b'"unterminated\n')


def test_source_byte_limit_is_checked_at_and_above_boundary() -> None:
    content = b"a\n1\n"
    assert (
        ingest(
            content,
            limits=ResourceLimits(max_source_bytes=len(content), max_rows=1, max_columns=1),
        ).row_count
        == 1
    )

    with pytest.raises(SourceTooLargeError) as raised:
        ingest(
            content,
            limits=ResourceLimits(max_source_bytes=len(content) - 1, max_rows=1, max_columns=1),
        )
    assert raised.value.actual_bytes == len(content)
    assert raised.value.max_bytes == len(content) - 1


def test_row_limit_is_checked_at_and_above_boundary() -> None:
    limits = ResourceLimits(max_source_bytes=100, max_rows=2, max_columns=1)
    assert ingest(b"a\n1\n2\n", limits=limits).row_count == 2

    with pytest.raises(RowLimitExceededError) as raised:
        ingest(b"a\n1\n2\n3\n", limits=limits)
    assert raised.value.observed_rows == 3
    assert raised.value.max_rows == 2


def test_column_limit_is_checked_at_and_above_boundary() -> None:
    limits = ResourceLimits(max_source_bytes=100, max_rows=1, max_columns=2)
    assert ingest(b"a,b\n1,2\n", limits=limits).column_count == 2

    with pytest.raises(ColumnLimitExceededError) as raised:
        ingest(b"a,b,c\n1,2,3\n", limits=limits)
    assert raised.value.observed_columns == 3
    assert raised.value.max_columns == 2


def test_duplicate_columns_are_rejected_before_pandas_can_rename_them() -> None:
    with pytest.raises(DuplicateColumnsError) as raised:
        ingest(b"name,name,value\nA,B,1\n")
    assert raised.value.duplicate_columns == ("name",)
    assert raised.value.code is IngestionErrorCode.DUPLICATE_COLUMNS


def test_unusual_valid_column_names_are_preserved_exactly() -> None:
    headers = [" customer id ", "Total (€)", "a.b", "日本語"]
    result = ingest(" customer id ,Total (€),a.b,日本語\n1,2,3,四\n".encode())
    assert list(result.table.columns) == headers


@pytest.mark.parametrize(
    ("content", "positions"),
    [
        (b",name\n1,A\n", (1,)),
        (b'name,"  "\n1,A\n', (2,)),
        (b", \n1,A\n", (1, 2)),
    ],
)
def test_empty_or_whitespace_only_headers_are_rejected_before_pandas(
    content: bytes, positions: tuple[int, ...]
) -> None:
    with pytest.raises(InvalidColumnNamesError) as raised:
        ingest(content)
    assert raised.value.code is IngestionErrorCode.INVALID_COLUMN_NAMES
    assert raised.value.column_positions == positions
    assert "Unnamed" not in raised.value.message


def test_missing_values_are_loaded_without_profiling_or_cleanup() -> None:
    result = ingest(b"name,value\nA,\n,2\n")
    assert pd.isna(result.table.loc[0, "value"])
    assert pd.isna(result.table.loc[1, "name"])
    assert result.row_count == 2


def test_mixed_content_ingests_without_semantic_type_inference() -> None:
    result = ingest(b"mixed,category\n1,A\ntwo,B\n3,C\n")
    assert result.table["mixed"].tolist() == ["1", "two", "3"]
    assert result.table["category"].tolist() == ["A", "B", "C"]


@pytest.mark.parametrize(
    ("source_name", "safe_name"),
    [
        ("../../secret.csv", "secret.csv"),
        ("....\\secret.csv", "secret.csv"),
        ("../windows\\nested/final.csv", "final.csv"),
        ("folder\\odd\n\tname.csv", "odd__name.csv"),
    ],
)
def test_untrusted_filename_is_portably_reduced_to_safe_display_metadata(
    source_name: str, safe_name: str
) -> None:
    result = ingest(b"a\n1\n", source_name=source_name)
    assert result.metadata.source_name == safe_name
    assert "/" not in result.metadata.source_name
    assert "\\" not in result.metadata.source_name


def test_excessively_long_filename_metadata_is_bounded() -> None:
    result = ingest(b"a\n1\n", source_name="folder/" + "x" * 300 + ".csv")
    assert len(result.metadata.source_name) == 255
    assert result.metadata.source_name == "x" * 255


def test_extension_is_not_trusted_when_content_is_valid_text() -> None:
    result = ingest(b"a,b\n1,2\n", source_name="payload.exe")
    assert result.row_count == 1
    assert result.metadata.source_name == "payload.exe"


def test_nul_bytes_are_rejected_as_implausible_csv_text() -> None:
    with pytest.raises(UnsupportedSourceError, match="NUL bytes") as raised:
        ingest(b"a,b\n1,\x002\n")
    assert raised.value.code is IngestionErrorCode.UNSUPPORTED_SOURCE


def test_csv_content_is_not_executed_or_transformed() -> None:
    result = ingest(b"formula\n=2+2\n")
    assert result.table.iloc[0, 0] == "=2+2"


def test_logs_contain_safe_metadata_but_not_csv_values(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    result = ingest(b"secret,value\nDO_NOT_LOG,42\n", source_name="folder/private.csv")
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert [record["event"] for record in records] == [
        "ingestion_started",
        "ingestion_succeeded",
    ]
    assert records[-1]["source_type"] == "csv"
    assert records[-1]["source_name"] == "private.csv"
    assert records[-1]["row_count"] == 1
    assert records[-1]["duration_ms"] >= 0
    assert "DO_NOT_LOG" not in json.dumps(records)
    assert result.row_count == 1


def test_failure_log_uses_error_code_without_raw_content(
    capsys: pytest.CaptureFixture[str],
) -> None:
    configure_logging("INFO")
    with pytest.raises(InvalidEncodingError):
        ingest(b"secret\n\xff\n")
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert records[-1]["event"] == "ingestion_failed"
    assert records[-1]["error_code"] == "invalid_encoding"
    assert records[-1]["duration_ms"] >= 0
    assert "secret" not in json.dumps(records)


def test_pandas_parser_failures_are_translated(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fail_parser(*args: object, **kwargs: object) -> pd.DataFrame:
        raise pd.errors.ParserError("raw parser detail")

    monkeypatch.setattr(pd, "read_csv", fail_parser)
    with pytest.raises(MalformedSourceError, match="parsed safely") as raised:
        ingest(b"a\n1\n")
    assert "raw parser detail" not in raised.value.message


def test_inconsistent_materialized_schema_is_rejected(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: pd.DataFrame({"changed": [1]}))
    with pytest.raises(IngestionConsistencyError) as raised:
        ingest(b"a\n1\n")
    assert raised.value.code is IngestionErrorCode.INGESTION_CONSISTENCY
    assert raised.value.expected_rows == raised.value.actual_rows == 1
    assert raised.value.expected_columns == raised.value.actual_columns == 1
    assert "changed" not in raised.value.message


@pytest.mark.parametrize(
    ("materialized", "actual_rows", "actual_columns"),
    [
        (pd.DataFrame({"a": [1, 2]}), 2, 1),
        (pd.DataFrame({"a": [1], "extra": [2]}), 1, 2),
    ],
)
def test_materialized_dimensions_must_match_structural_counts(
    monkeypatch: pytest.MonkeyPatch,
    materialized: pd.DataFrame,
    actual_rows: int,
    actual_columns: int,
) -> None:
    monkeypatch.setattr(pd, "read_csv", lambda *args, **kwargs: materialized)
    with pytest.raises(IngestionConsistencyError) as raised:
        ingest(b"a\n1\n")
    assert raised.value.expected_rows == 1
    assert raised.value.actual_rows == actual_rows
    assert raised.value.expected_columns == 1
    assert raised.value.actual_columns == actual_columns
