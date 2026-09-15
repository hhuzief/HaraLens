"""Strict, bounded CSV ingestion from caller-owned bytes."""

import csv
import io
import logging
import time
from collections.abc import Iterator

import pandas as pd

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
    InvalidEncodingError,
    MalformedSourceError,
    NoDataRowsError,
    RowLimitExceededError,
    UnsupportedSourceError,
)
from haralens.ingestion.models import (
    IngestionMetadata,
    IngestionRequest,
    IngestionResult,
    SourceType,
)

_UTF8_BOM = b"\xef\xbb\xbf"


def _usable_rows(reader: Iterator[list[str]]) -> Iterator[list[str]]:
    return (row for row in reader if row)


class CsvIngestionAdapter:
    """Load strict comma-delimited UTF-8 CSV without truncation or schema rewriting."""

    source_type = SourceType.CSV

    def __init__(self) -> None:
        self._logger = logging.getLogger("haralens.ingestion.csv")

    def ingest(self, request: IngestionRequest) -> IngestionResult:
        started = time.perf_counter()
        safe_name = safe_display_name(request.source_name, fallback="unnamed.csv")
        source_bytes = len(request.content)
        log_data: dict[str, object] = {
            "source_type": self.source_type.value,
            "source_name": safe_name,
            "source_bytes": source_bytes,
        }
        self._logger.info("ingestion_started", extra={"event_data": log_data})
        try:
            table, encoding = self._load(request)
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
            source_type=SourceType.CSV,
            source_name=safe_name,
            source_bytes=source_bytes,
            encoding=encoding,
            duration_ms=duration_ms,
        )
        self._logger.info(
            "ingestion_succeeded",
            extra={
                "event_data": {
                    **log_data,
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

    def _load(self, request: IngestionRequest) -> tuple[pd.DataFrame, str]:
        source_bytes = len(request.content)
        enforce_source_size(request.content, maximum=request.limits.max_source_bytes)
        if source_bytes == 0:
            raise EmptySourceError("The CSV source is empty (zero bytes).")

        encoding = "utf-8-sig" if request.content.startswith(_UTF8_BOM) else "utf-8"
        try:
            text = request.content.decode(encoding, errors="strict")
        except UnicodeDecodeError as error:
            raise InvalidEncodingError(
                "The CSV must use UTF-8 encoding; convert the file to UTF-8 and try again."
            ) from error

        if not text.strip():
            raise EmptySourceError("The CSV contains no usable rows.")
        if "\x00" in text:
            raise UnsupportedSourceError(
                "The source contains NUL bytes and is not supported as CSV text."
            )

        try:
            rows = _usable_rows(iter(csv.reader(io.StringIO(text, newline=""), strict=True)))
            header = next(rows)
        except StopIteration as error:
            raise EmptySourceError("The CSV contains no usable rows.") from error
        except csv.Error as error:
            raise MalformedSourceError(
                "The CSV structure is malformed; check quoting and rows."
            ) from error

        column_count = len(header)
        if column_count > request.limits.max_columns:
            raise ColumnLimitExceededError(
                observed_columns=column_count, max_columns=request.limits.max_columns
            )

        validate_text_columns(header)

        row_count = 0
        try:
            for row in rows:
                row_count += 1
                if len(row) != column_count:
                    raise MalformedSourceError(
                        "The CSV has inconsistent row widths; no rows were loaded."
                    )
                if row_count > request.limits.max_rows:
                    raise RowLimitExceededError(
                        observed_rows=row_count, max_rows=request.limits.max_rows
                    )
        except csv.Error as error:
            raise MalformedSourceError(
                "The CSV structure is malformed; check quoting and rows."
            ) from error

        if row_count == 0:
            raise NoDataRowsError("The CSV contains a header but no data rows.")

        try:
            table = pd.read_csv(io.StringIO(text), sep=",", encoding_errors="strict")
        except (pd.errors.ParserError, ValueError) as error:
            raise MalformedSourceError("The CSV could not be parsed safely.") from error

        enforce_materialization_invariant(table, expected_rows=row_count, expected_columns=header)
        return table, encoding
