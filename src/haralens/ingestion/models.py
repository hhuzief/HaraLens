"""Typed ingestion inputs, resource policy and structured results."""

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from typing import Annotated
from uuid import UUID, uuid4

import pandas as pd
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

SourceName = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
SafeSourceName = Annotated[str, StringConstraints(min_length=1, max_length=255)]


class SourceType(StrEnum):
    CSV = "csv"


class ResourceLimits(BaseModel):
    """Hard ingestion limits. Exceeding one always rejects the whole source."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    max_source_bytes: int = Field(gt=0)
    max_rows: int = Field(gt=0)
    max_columns: int = Field(gt=0)


class IngestionRequest(BaseModel):
    """In-memory source supplied by a trusted boundary such as a future upload service."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    content: bytes
    source_name: SourceName = "unnamed.csv"
    limits: ResourceLimits


class IngestionMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    source_type: SourceType
    source_name: SafeSourceName
    source_bytes: int = Field(ge=0)
    encoding: str
    ingested_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = Field(ge=0)


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """A table plus serializable metadata; profiling is intentionally absent."""

    table: pd.DataFrame
    row_count: int
    column_count: int
    metadata: IngestionMetadata
