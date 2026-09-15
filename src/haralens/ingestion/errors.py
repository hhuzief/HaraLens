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
    UNSUPPORTED_WORKBOOK_FORMAT = "unsupported_workbook_format"
    MALFORMED_WORKBOOK = "malformed_workbook"
    ARCHIVE_SAFETY_VIOLATION = "archive_safety_violation"
    WORKBOOK_LIMIT_EXCEEDED = "workbook_limit_exceeded"
    WORKSHEET_SELECTION_REQUIRED = "worksheet_selection_required"
    WORKSHEET_NOT_FOUND = "worksheet_not_found"
    NO_USABLE_WORKSHEET = "no_usable_worksheet"
    EMPTY_WORKSHEET = "empty_worksheet"
    UNSUPPORTED_WORKSHEET_STRUCTURE = "unsupported_worksheet_structure"
    MALFORMED_PARQUET = "malformed_parquet"
    PARQUET_LIMIT_EXCEEDED = "parquet_limit_exceeded"
    UNSUPPORTED_PARQUET_SCHEMA = "unsupported_parquet_schema"


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


class UnsupportedWorkbookFormatError(IngestionError):
    code = IngestionErrorCode.UNSUPPORTED_WORKBOOK_FORMAT


class MalformedWorkbookError(IngestionError):
    code = IngestionErrorCode.MALFORMED_WORKBOOK


class ArchiveSafetyError(IngestionError):
    code = IngestionErrorCode.ARCHIVE_SAFETY_VIOLATION


class WorkbookLimitExceededError(IngestionError):
    code = IngestionErrorCode.WORKBOOK_LIMIT_EXCEEDED

    def __init__(self, *, resource: str, observed: int, maximum: int) -> None:
        self.resource = resource
        self.observed = observed
        self.maximum = maximum
        super().__init__(f"The workbook exceeds the configured {resource} limit of {maximum}.")


class WorksheetSelectionRequiredError(IngestionError):
    code = IngestionErrorCode.WORKSHEET_SELECTION_REQUIRED

    def __init__(self, *, available_worksheets: tuple[str, ...]) -> None:
        self.available_worksheets = available_worksheets
        super().__init__(
            "The workbook has multiple usable visible worksheets; select one explicitly."
        )


class WorksheetNotFoundError(IngestionError):
    code = IngestionErrorCode.WORKSHEET_NOT_FOUND

    def __init__(self, *, available_worksheets: tuple[str, ...]) -> None:
        self.available_worksheets = available_worksheets
        super().__init__("The requested worksheet does not exist in this workbook.")


class NoUsableWorksheetError(IngestionError):
    code = IngestionErrorCode.NO_USABLE_WORKSHEET


class EmptyWorksheetError(IngestionError):
    code = IngestionErrorCode.EMPTY_WORKSHEET


class UnsupportedWorksheetStructureError(IngestionError):
    code = IngestionErrorCode.UNSUPPORTED_WORKSHEET_STRUCTURE


class MalformedParquetError(IngestionError):
    code = IngestionErrorCode.MALFORMED_PARQUET


class ParquetLimitExceededError(IngestionError):
    code = IngestionErrorCode.PARQUET_LIMIT_EXCEEDED

    def __init__(self, *, resource: str, observed: int, maximum: int) -> None:
        self.resource = resource
        self.observed = observed
        self.maximum = maximum
        super().__init__(
            f"The Parquet source exceeds the configured {resource} limit of {maximum}."
        )


class UnsupportedParquetSchemaError(IngestionError):
    code = IngestionErrorCode.UNSUPPORTED_PARQUET_SCHEMA

    def __init__(self, *, unsupported_columns: tuple[str, ...]) -> None:
        self.unsupported_columns = unsupported_columns
        super().__init__("The Parquet schema contains nested columns that are not supported.")


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
        super().__init__("The source contains duplicate column names; make each name unique.")


class InvalidColumnNamesError(IngestionError):
    code = IngestionErrorCode.INVALID_COLUMN_NAMES

    def __init__(self, *, column_positions: tuple[int, ...]) -> None:
        self.column_positions = column_positions
        super().__init__(
            "The source contains invalid, empty, or whitespace-only column names; "
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
            "The materialized table does not match the validated source structure; "
            "no ingestion result was returned."
        )
