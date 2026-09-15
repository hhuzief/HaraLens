"""Typed ingestion inputs, resource policy and structured results."""

from dataclasses import dataclass
from datetime import UTC, date, datetime
from enum import StrEnum
from typing import Annotated, Literal
from uuid import UUID, uuid4

import pandas as pd
from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, StringConstraints

SourceName = Annotated[str, StringConstraints(min_length=1, max_length=4096)]
SafeSourceName = Annotated[str, StringConstraints(min_length=1, max_length=255)]
ExcelHeaderScalar = str | bool | int | float | date | datetime


class SourceType(StrEnum):
    CSV = "csv"
    XLSX = "xlsx"
    PARQUET = "parquet"


class ResourceLimits(BaseModel):
    """Hard ingestion limits. Exceeding one always rejects the whole source."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    max_source_bytes: int = Field(gt=0)
    max_rows: int = Field(gt=0)
    max_columns: int = Field(gt=0)
    max_xlsx_archive_entries: int = Field(default=1_000, gt=0)
    max_xlsx_uncompressed_bytes: int = Field(default=100 * 1024 * 1024, gt=0)
    max_xlsx_compression_ratio: float = Field(default=200.0, gt=0)
    max_xlsx_worksheets: int = Field(default=100, gt=0)
    max_xlsx_cells: int = Field(default=1_000_000, gt=0)
    max_parquet_metadata_bytes: int = Field(default=8 * 1024 * 1024, gt=0)
    max_parquet_row_groups: int = Field(default=1_000, gt=0)


class IngestionRequest(BaseModel):
    """In-memory source supplied by a trusted boundary such as a future upload service."""

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True)

    content: bytes
    source_name: SourceName = "unnamed.csv"
    limits: ResourceLimits
    worksheet_name: Annotated[str, StringConstraints(min_length=1, max_length=31)] | None = None


class ExcelFormatMetadata(BaseModel):
    """Serializable XLSX details retained with a successful result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    workbook_format: Literal["xlsx"] = "xlsx"
    selected_worksheet: str
    worksheet_count: int = Field(ge=1)
    visible_worksheet_count: int = Field(ge=0)
    formula_representation: Literal["formula_text"] = "formula_text"
    original_column_headers: tuple[ExcelHeaderScalar, ...]


class ParquetFormatMetadata(BaseModel):
    """Serializable Parquet details retained with a successful result."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    row_group_count: int = Field(ge=0)
    format_version: str
    schema_summary: tuple[str, ...]


class IngestionMetadata(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    run_id: UUID = Field(default_factory=uuid4)
    source_type: SourceType
    source_name: SafeSourceName
    source_bytes: int = Field(ge=0)
    encoding: str | None
    ingested_at: AwareDatetime = Field(default_factory=lambda: datetime.now(UTC))
    duration_ms: float = Field(ge=0)
    format_metadata: ExcelFormatMetadata | ParquetFormatMetadata | None = None


@dataclass(frozen=True, slots=True)
class IngestionResult:
    """A table plus serializable metadata; profiling is intentionally absent."""

    table: pd.DataFrame
    row_count: int
    column_count: int
    metadata: IngestionMetadata
