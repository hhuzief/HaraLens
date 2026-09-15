"""Reusable, presentation-independent ingestion contracts and adapters."""

from haralens.ingestion.contracts import IngestionAdapter
from haralens.ingestion.csv import CsvIngestionAdapter
from haralens.ingestion.errors import (
    ColumnLimitExceededError,
    DuplicateColumnsError,
    EmptySourceError,
    IngestionConsistencyError,
    IngestionError,
    InvalidColumnNamesError,
    InvalidEncodingError,
    MalformedSourceError,
    NoDataRowsError,
    RowLimitExceededError,
    SourceTooLargeError,
    UnsupportedSourceError,
)
from haralens.ingestion.models import (
    IngestionMetadata,
    IngestionRequest,
    IngestionResult,
    ResourceLimits,
    SourceType,
)

__all__ = [
    "CsvIngestionAdapter",
    "ColumnLimitExceededError",
    "DuplicateColumnsError",
    "EmptySourceError",
    "IngestionAdapter",
    "IngestionConsistencyError",
    "IngestionError",
    "IngestionMetadata",
    "IngestionRequest",
    "IngestionResult",
    "InvalidColumnNamesError",
    "InvalidEncodingError",
    "MalformedSourceError",
    "NoDataRowsError",
    "ResourceLimits",
    "RowLimitExceededError",
    "SourceType",
    "SourceTooLargeError",
    "UnsupportedSourceError",
]
