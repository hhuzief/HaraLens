import io
import json
import struct
from datetime import UTC, datetime

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
import pytest

from haralens.common.logging import configure_logging
from haralens.ingestion.csv import CsvIngestionAdapter
from haralens.ingestion.errors import (
    ColumnLimitExceededError,
    DuplicateColumnsError,
    EmptySourceError,
    IngestionConsistencyError,
    IngestionError,
    InvalidColumnNamesError,
    MalformedParquetError,
    NoDataRowsError,
    ParquetLimitExceededError,
    RowLimitExceededError,
    SourceTooLargeError,
    UnsupportedParquetSchemaError,
)
from haralens.ingestion.models import (
    IngestionRequest,
    ParquetFormatMetadata,
    ResourceLimits,
    SourceType,
)
from haralens.ingestion.parquet import ParquetIngestionAdapter

DEFAULT_LIMITS = ResourceLimits(max_source_bytes=1_000_000, max_rows=100, max_columns=20)


def parquet_bytes(table: pa.Table, *, row_group_size: int | None = None) -> bytes:
    output = io.BytesIO()
    pq.write_table(table, output, row_group_size=row_group_size)
    return output.getvalue()


def ingest(
    content: bytes,
    *,
    source_name: str = "data.parquet",
    limits: ResourceLimits = DEFAULT_LIMITS,
):
    return ParquetIngestionAdapter().ingest(
        IngestionRequest(content=content, source_name=source_name, limits=limits)
    )


def test_valid_parquet_preserves_basic_types_nulls_and_metadata() -> None:
    timestamp = datetime(2025, 1, 2, 3, 4, tzinfo=UTC)
    table = pa.table(
        {
            "number": pa.array([1, None], type=pa.int64()),
            "text": ["A", "B"],
            "active": [True, False],
            "when": pa.array([timestamp, None], type=pa.timestamp("us", tz="UTC")),
        }
    )
    content = parquet_bytes(table)

    result = ingest(content)

    assert result.row_count == 2
    assert result.column_count == 4
    assert list(result.table.columns) == table.column_names
    assert result.table["text"].tolist() == ["A", "B"]
    assert pd.isna(result.table.loc[1, "number"])
    assert result.table.loc[0, "when"] == timestamp
    assert result.metadata.source_type is SourceType.PARQUET
    assert result.metadata.encoding is None
    assert isinstance(result.metadata.format_metadata, ParquetFormatMetadata)
    assert result.metadata.format_metadata.row_group_count == 1
    assert result.metadata.format_metadata.format_version
    assert result.metadata.format_metadata.schema_summary[0].startswith("number: int64")


def test_dictionary_encoded_values_materialize_without_semantic_inference() -> None:
    dictionary = pa.array(["red", "blue"]).dictionary_encode()
    result = ingest(parquet_bytes(pa.table({"category": dictionary})))
    assert result.table["category"].tolist() == ["red", "blue"]


def test_row_and_column_limits_use_metadata_before_materialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = parquet_bytes(pa.table({"a": [1, 2], "b": [3, 4]}))

    def forbidden_materialization(table: pa.Table) -> pd.DataFrame:
        raise AssertionError("materialization must not occur")

    monkeypatch.setattr("haralens.ingestion.parquet._to_pandas", forbidden_materialization)
    with pytest.raises(RowLimitExceededError):
        ingest(
            content,
            limits=ResourceLimits(max_source_bytes=len(content), max_rows=1, max_columns=2),
        )
    with pytest.raises(ColumnLimitExceededError):
        ingest(
            content,
            limits=ResourceLimits(max_source_bytes=len(content), max_rows=2, max_columns=1),
        )


def test_source_byte_limit_accepts_boundary_and_rejects_above_it() -> None:
    content = parquet_bytes(pa.table({"a": [1]}))
    assert (
        ingest(
            content,
            limits=ResourceLimits(max_source_bytes=len(content), max_rows=1, max_columns=1),
        ).row_count
        == 1
    )
    with pytest.raises(SourceTooLargeError):
        ingest(
            content,
            limits=ResourceLimits(max_source_bytes=len(content) - 1, max_rows=1, max_columns=1),
        )


def test_empty_table_and_zero_column_table_fail_predictably() -> None:
    with pytest.raises(NoDataRowsError):
        ingest(parquet_bytes(pa.table({"a": pa.array([], type=pa.int64())})))
    with pytest.raises(EmptySourceError):
        ingest(parquet_bytes(pa.table({})))


def test_duplicate_empty_and_whitespace_column_names_are_rejected() -> None:
    duplicate = pa.Table.from_arrays([pa.array([1]), pa.array([2])], names=["a", "a"])
    with pytest.raises(DuplicateColumnsError):
        ingest(parquet_bytes(duplicate))

    for name in ("", "   "):
        with pytest.raises(InvalidColumnNamesError) as raised:
            ingest(parquet_bytes(pa.table({name: [1]})))
        assert raised.value.column_positions == (1,)


def test_unusual_names_and_schema_order_are_preserved() -> None:
    names = [" customer id ", "Total (€)", "a.b", "日本語"]
    table = pa.Table.from_arrays([pa.array([index]) for index in range(4)], names=names)
    result = ingest(parquet_bytes(table))
    assert list(result.table.columns) == names
    assert result.table.iloc[0].tolist() == [0, 1, 2, 3]


@pytest.mark.parametrize("content", [b"", b"arbitrary bytes", b"PAR1bad footerPAR1"])
def test_malformed_and_fake_parquet_sources_fail_safely(content: bytes) -> None:
    expected = EmptySourceError if not content else MalformedParquetError
    with pytest.raises(expected):
        ingest(content)


def test_footer_metadata_size_limit_is_checked_before_pyarrow(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = parquet_bytes(pa.table({"a": [1]}))
    footer_size = struct.unpack("<I", content[-8:-4])[0]

    def forbidden_reader(*args: object, **kwargs: object) -> None:
        raise AssertionError("PyArrow must not be invoked")

    monkeypatch.setattr(pq, "ParquetFile", forbidden_reader)
    with pytest.raises(ParquetLimitExceededError) as raised:
        ingest(
            content,
            limits=ResourceLimits(
                max_source_bytes=len(content),
                max_rows=1,
                max_columns=1,
                max_parquet_metadata_bytes=footer_size - 1,
            ),
        )
    assert raised.value.resource == "metadata size"


def test_multiple_row_groups_are_supported_and_bounded() -> None:
    content = parquet_bytes(pa.table({"a": list(range(5))}), row_group_size=2)
    result = ingest(content)
    assert result.metadata.format_metadata.row_group_count == 3
    assert result.table["a"].tolist() == list(range(5))

    with pytest.raises(ParquetLimitExceededError) as raised:
        ingest(
            content,
            limits=ResourceLimits(
                max_source_bytes=len(content),
                max_rows=5,
                max_columns=1,
                max_parquet_row_groups=2,
            ),
        )
    assert raised.value.resource == "row-group count"


@pytest.mark.parametrize(
    "table",
    [
        pa.table({"nested": pa.array([[1, 2]], type=pa.list_(pa.int64()))}),
        pa.table(
            {
                "nested": pa.array(
                    [{"left": 1, "right": "x"}],
                    type=pa.struct([("left", pa.int64()), ("right", pa.string())]),
                )
            }
        ),
        pa.table({"nested": pa.array([[("key", 1)]], type=pa.map_(pa.string(), pa.int64()))}),
    ],
)
def test_nested_list_struct_and_map_schemas_are_rejected(table: pa.Table) -> None:
    with pytest.raises(UnsupportedParquetSchemaError) as raised:
        ingest(parquet_bytes(table))
    assert raised.value.unsupported_columns == ("nested",)


def test_materialization_invariant_rejects_shape_and_order_changes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = parquet_bytes(pa.table({"a": [1], "b": [2]}))
    monkeypatch.setattr(
        "haralens.ingestion.parquet._to_pandas",
        lambda table: pd.DataFrame({"b": [2], "a": [1]}),
    )
    with pytest.raises(IngestionConsistencyError):
        ingest(content)


def test_extension_is_not_trusted_and_source_name_is_sanitized() -> None:
    content = parquet_bytes(pa.table({"a": [1]}))
    result = ingest(content, source_name="../windows\\odd\n\tname.csv")
    assert result.metadata.source_name == "odd__name.csv"
    assert result.row_count == 1


def test_parquet_content_is_not_accepted_by_the_csv_adapter() -> None:
    content = parquet_bytes(pa.table({"a": [1]}))
    with pytest.raises(IngestionError):
        CsvIngestionAdapter().ingest(
            IngestionRequest(content=content, source_name="data.csv", limits=DEFAULT_LIMITS)
        )


def test_parser_failure_is_translated_without_raw_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    content = parquet_bytes(pa.table({"a": [1]}))

    class BrokenReader:
        def __init__(self, *args: object, **kwargs: object) -> None:
            raise pa.ArrowInvalid("raw sensitive parser detail")

    monkeypatch.setattr(pq, "ParquetFile", BrokenReader)
    with pytest.raises(MalformedParquetError) as raised:
        ingest(content)
    assert "sensitive" not in raised.value.message
    assert raised.value.__cause__ is not None


def test_logs_exclude_values(capsys: pytest.CaptureFixture[str]) -> None:
    configure_logging("INFO")
    content = parquet_bytes(pa.table({"secret": ["DO_NOT_LOG"]}))
    ingest(content, source_name="folder/private.parquet")
    records = [json.loads(line) for line in capsys.readouterr().err.splitlines()]
    assert records[-1]["row_group_count"] == 1
    assert records[-1]["source_name"] == "private.parquet"
    assert "DO_NOT_LOG" not in json.dumps(records)
