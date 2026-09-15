"""Metadata-first bounded Parquet ingestion from caller-owned bytes."""

import logging
import struct
import time

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from haralens.ingestion._shared import (
    enforce_materialization_invariant,
    enforce_source_size,
    safe_display_name,
    validate_text_columns,
)
from haralens.ingestion.errors import (
    ColumnLimitExceededError,
    EmptySourceError,
    IngestionError,
    MalformedParquetError,
    NoDataRowsError,
    ParquetLimitExceededError,
    RowLimitExceededError,
    UnsupportedParquetSchemaError,
)
from haralens.ingestion.models import (
    IngestionMetadata,
    IngestionRequest,
    IngestionResult,
    ParquetFormatMetadata,
    SourceType,
)

_PARQUET_MAGIC = b"PAR1"
_MINIMUM_PARQUET_BYTES = 12


def _validate_footer(content: bytes, *, maximum_metadata_bytes: int) -> None:
    if (
        len(content) < _MINIMUM_PARQUET_BYTES
        or content[:4] != _PARQUET_MAGIC
        or content[-4:] != _PARQUET_MAGIC
    ):
        raise MalformedParquetError("The source is not a valid Parquet container.")

    metadata_bytes = struct.unpack("<I", content[-8:-4])[0]
    if metadata_bytes + 8 > len(content) - 4:
        raise MalformedParquetError("The Parquet footer length is invalid.")
    if metadata_bytes > maximum_metadata_bytes:
        raise ParquetLimitExceededError(
            resource="metadata size",
            observed=metadata_bytes,
            maximum=maximum_metadata_bytes,
        )


def _nested_columns(schema: pa.Schema) -> tuple[str, ...]:
    return tuple(field.name for field in schema if pa.types.is_nested(field.type))


def _to_pandas(table: pa.Table) -> pd.DataFrame:
    return table.to_pandas(
        ignore_metadata=True,
        use_threads=False,
        safe=True,
    )


class ParquetIngestionAdapter:
    """Load a flat Parquet table after validating its footer metadata."""

    source_type = SourceType.PARQUET

    def __init__(self) -> None:
        self._logger = logging.getLogger("haralens.ingestion.parquet")

    def ingest(self, request: IngestionRequest) -> IngestionResult:
        started = time.perf_counter()
        safe_name = safe_display_name(request.source_name, fallback="unnamed.parquet")
        source_bytes = len(request.content)
        log_data: dict[str, object] = {
            "source_type": self.source_type.value,
            "source_name": safe_name,
            "source_bytes": source_bytes,
        }
        self._logger.info("ingestion_started", extra={"event_data": log_data})
        try:
            table, format_metadata = self._load(request)
        except IngestionError as error:
            duration_ms = (time.perf_counter() - started) * 1_000
            self._logger.warning(
                "ingestion_failed",
                extra={
                    "event_data": {
                        **log_data,
                        "error_code": error.code.value,
                        "duration_ms": round(duration_ms, 3),
                    }
                },
            )
            raise

        duration_ms = (time.perf_counter() - started) * 1_000
        metadata = IngestionMetadata(
            source_type=self.source_type,
            source_name=safe_name,
            source_bytes=source_bytes,
            encoding=None,
            duration_ms=duration_ms,
            format_metadata=format_metadata,
        )
        self._logger.info(
            "ingestion_succeeded",
            extra={
                "event_data": {
                    **log_data,
                    "row_group_count": format_metadata.row_group_count,
                    "row_count": len(table.index),
                    "column_count": len(table.columns),
                    "duration_ms": round(duration_ms, 3),
                }
            },
        )
        return IngestionResult(
            table=table,
            row_count=len(table.index),
            column_count=len(table.columns),
            metadata=metadata,
        )

    def _load(self, request: IngestionRequest) -> tuple[pd.DataFrame, ParquetFormatMetadata]:
        enforce_source_size(request.content, maximum=request.limits.max_source_bytes)
        if not request.content:
            raise EmptySourceError("The Parquet source is empty (zero bytes).")
        _validate_footer(
            request.content,
            maximum_metadata_bytes=request.limits.max_parquet_metadata_bytes,
        )

        reader: pq.ParquetFile | None = None
        try:
            reader = pq.ParquetFile(
                pa.BufferReader(request.content),
                pre_buffer=False,
                thrift_string_size_limit=request.limits.max_parquet_metadata_bytes,
                thrift_container_size_limit=max(
                    1_024,
                    request.limits.max_columns * 8 + request.limits.max_parquet_row_groups * 4,
                ),
                page_checksum_verification=True,
            )
            metadata = reader.metadata
            row_count = metadata.num_rows
            row_group_count = metadata.num_row_groups
            schema = reader.schema_arrow
            column_count = len(schema)

            if row_count > request.limits.max_rows:
                raise RowLimitExceededError(
                    observed_rows=row_count, max_rows=request.limits.max_rows
                )
            if column_count > request.limits.max_columns:
                raise ColumnLimitExceededError(
                    observed_columns=column_count,
                    max_columns=request.limits.max_columns,
                )
            if row_group_count > request.limits.max_parquet_row_groups:
                raise ParquetLimitExceededError(
                    resource="row-group count",
                    observed=row_group_count,
                    maximum=request.limits.max_parquet_row_groups,
                )
            if column_count == 0:
                raise EmptySourceError("The Parquet table contains no columns.")
            if row_count == 0:
                raise NoDataRowsError("The Parquet table contains columns but no data rows.")

            columns = validate_text_columns(schema.names)
            unsupported = _nested_columns(schema)
            if unsupported:
                raise UnsupportedParquetSchemaError(unsupported_columns=unsupported)

            arrow_table = reader.read(use_threads=False, use_pandas_metadata=False)
            table = _to_pandas(arrow_table)
            enforce_materialization_invariant(
                table,
                expected_rows=row_count,
                expected_columns=columns,
            )
            return table, ParquetFormatMetadata(
                row_group_count=row_group_count,
                format_version=metadata.format_version,
                schema_summary=tuple(f"{field.name}: {field.type}" for field in schema),
            )
        except IngestionError:
            raise
        except (pa.ArrowException, OSError, OverflowError, ValueError) as error:
            raise MalformedParquetError("The Parquet source could not be parsed safely.") from error
        finally:
            if reader is not None:
                reader.close()
