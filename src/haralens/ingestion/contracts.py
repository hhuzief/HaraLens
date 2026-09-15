"""Interface implemented by bounded source-specific ingestion adapters."""

from typing import Protocol

from haralens.ingestion.models import IngestionRequest, IngestionResult, SourceType


class IngestionAdapter(Protocol):
    source_type: SourceType

    def ingest(self, request: IngestionRequest) -> IngestionResult:
        """Load a source or raise a typed, safe ingestion error."""
        ...
