"""Safe, typed failures for application-service translation."""

from enum import StrEnum


class IngestionErrorCode(StrEnum):
    UNSUPPORTED_SOURCE = "unsupported_source"
    SOURCE_TOO_LARGE = "source_too_large"
    EMPTY_SOURCE = "empty_source"
    NO_DATA_ROWS = "no_data_rows"
    INVALID_ENCODING = "invalid_encoding"
    MALFORMED_SOURCE = "malformed_source"
    ROW_LIMIT_EXCEEDED = "row_limit_exceeded"
    COLUMN_LIMIT_EXCEEDED = "column_limit_exceeded"
    DUPLICATE_COLUMNS = "duplicate_columns"
    INVALID_COLUMN_NAMES = "invalid_column_names"
    INGESTION_CONSISTENCY = "ingestion_consistency"


class IngestionError(Exception):
    """Base error with a stable code and safe user-facing message."""

    code: IngestionErrorCode

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class UnsupportedSourceError(IngestionError):
    code = IngestionErrorCode.UNSUPPORTED_SOURCE


class SourceTooLargeError(IngestionError):
    code = IngestionErrorCode.SOURCE_TOO_LARGE

    def __init__(self, *, actual_bytes: int, max_bytes: int) -> None:
        self.actual_bytes = actual_bytes
        self.max_bytes = max_bytes
        super().__init__(
            f"The source is {actual_bytes} bytes; the configured limit is {max_bytes} bytes."
        )


class EmptySourceError(IngestionError):
    code = IngestionErrorCode.EMPTY_SOURCE


class NoDataRowsError(IngestionError):
    code = IngestionErrorCode.NO_DATA_ROWS


class InvalidEncodingError(IngestionError):
    code = IngestionErrorCode.INVALID_ENCODING


class MalformedSourceError(IngestionError):
    code = IngestionErrorCode.MALFORMED_SOURCE


class RowLimitExceededError(IngestionError):
    code = IngestionErrorCode.ROW_LIMIT_EXCEEDED

    def __init__(self, *, observed_rows: int, max_rows: int) -> None:
        self.observed_rows = observed_rows
        self.max_rows = max_rows
        super().__init__(
            f"The source has more than {max_rows} data rows; "
            "reduce it or raise the configured limit."
        )


class ColumnLimitExceededError(IngestionError):
    code = IngestionErrorCode.COLUMN_LIMIT_EXCEEDED

    def __init__(self, *, observed_columns: int, max_columns: int) -> None:
        self.observed_columns = observed_columns
        self.max_columns = max_columns
        super().__init__(
            f"The source has {observed_columns} columns; the configured limit is {max_columns}."
        )


class DuplicateColumnsError(IngestionError):
    code = IngestionErrorCode.DUPLICATE_COLUMNS

    def __init__(self, *, duplicate_columns: tuple[str, ...]) -> None:
        self.duplicate_columns = duplicate_columns
        super().__init__("The CSV header contains duplicate column names; make each name unique.")


class InvalidColumnNamesError(IngestionError):
    code = IngestionErrorCode.INVALID_COLUMN_NAMES

    def __init__(self, *, column_positions: tuple[int, ...]) -> None:
        self.column_positions = column_positions
        super().__init__(
            "The CSV header contains empty or whitespace-only column names; "
            "provide a nonempty name for every column."
        )


class IngestionConsistencyError(IngestionError):
    code = IngestionErrorCode.INGESTION_CONSISTENCY

    def __init__(
        self,
        *,
        expected_rows: int,
        actual_rows: int,
        expected_columns: int,
        actual_columns: int,
    ) -> None:
        self.expected_rows = expected_rows
        self.actual_rows = actual_rows
        self.expected_columns = expected_columns
        self.actual_columns = actual_columns
        super().__init__(
            "The materialized table does not match the structurally validated CSV; "
            "no ingestion result was returned."
        )
