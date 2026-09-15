from datetime import datetime

import pytest
from pydantic import ValidationError

from haralens.ingestion.models import IngestionRequest, ResourceLimits


@pytest.mark.parametrize("field", ["max_source_bytes", "max_rows", "max_columns"])
@pytest.mark.parametrize("value", [0, -1])
def test_resource_limits_reject_nonpositive_values(field: str, value: int) -> None:
    values = {"max_source_bytes": 10, "max_rows": 10, "max_columns": 10, field: value}
    with pytest.raises(ValidationError):
        ResourceLimits(**values)


def test_resource_limits_reject_coerced_numbers() -> None:
    with pytest.raises(ValidationError):
        ResourceLimits(max_source_bytes="10", max_rows=10, max_columns=10)


def test_request_rejects_empty_or_excessive_source_name() -> None:
    limits = ResourceLimits(max_source_bytes=10, max_rows=10, max_columns=10)
    with pytest.raises(ValidationError):
        IngestionRequest(content=b"x", source_name="", limits=limits)
    with pytest.raises(ValidationError):
        IngestionRequest(content=b"x", source_name="x" * 4097, limits=limits)


def test_request_requires_bytes_without_coercion() -> None:
    limits = ResourceLimits(max_source_bytes=10, max_rows=10, max_columns=10)
    with pytest.raises(ValidationError):
        IngestionRequest(content="a\n1\n", limits=limits)


def test_ingestion_timestamps_are_timezone_aware() -> None:
    from haralens.ingestion.models import IngestionMetadata, SourceType

    metadata = IngestionMetadata(
        source_type=SourceType.CSV,
        source_name="data.csv",
        source_bytes=1,
        encoding="utf-8",
        duration_ms=0,
    )
    assert isinstance(metadata.ingested_at, datetime)
    assert metadata.ingested_at.tzinfo is not None
