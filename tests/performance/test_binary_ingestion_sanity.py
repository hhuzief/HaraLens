import io
import time

import pyarrow as pa
import pyarrow.parquet as pq
from openpyxl import Workbook

from haralens.ingestion.models import IngestionRequest, ResourceLimits
from haralens.ingestion.parquet import ParquetIngestionAdapter
from haralens.ingestion.xlsx import XlsxIngestionAdapter


def test_2k_row_xlsx_completes_within_sanity_budget() -> None:
    """Catch catastrophic regressions; this is not a throughput benchmark."""
    workbook = Workbook(write_only=True)
    worksheet = workbook.create_sheet("Data")
    worksheet.append(["id", "category", "value"])
    for index in range(2_000):
        worksheet.append([index, f"group-{index % 10}", index * 2])
    output = io.BytesIO()
    workbook.save(output)
    content = output.getvalue()
    request = IngestionRequest(
        content=content,
        source_name="synthetic-2k.xlsx",
        limits=ResourceLimits(
            max_source_bytes=len(content),
            max_rows=2_000,
            max_columns=3,
        ),
    )

    started = time.perf_counter()
    result = XlsxIngestionAdapter().ingest(request)
    elapsed = time.perf_counter() - started

    assert result.row_count == 2_000
    assert result.column_count == 3
    assert elapsed < 15, f"2k-row XLSX sanity load took {elapsed:.2f}s"


def test_20k_row_parquet_completes_within_sanity_budget() -> None:
    """Catch catastrophic regressions; this is not a throughput benchmark."""
    table = pa.table(
        {
            "id": list(range(20_000)),
            "category": [f"group-{index % 10}" for index in range(20_000)],
            "value": [index * 2 for index in range(20_000)],
        }
    )
    output = io.BytesIO()
    pq.write_table(table, output, row_group_size=5_000)
    content = output.getvalue()
    request = IngestionRequest(
        content=content,
        source_name="synthetic-20k.parquet",
        limits=ResourceLimits(
            max_source_bytes=len(content),
            max_rows=20_000,
            max_columns=3,
        ),
    )

    started = time.perf_counter()
    result = ParquetIngestionAdapter().ingest(request)
    elapsed = time.perf_counter() - started

    assert result.row_count == 20_000
    assert result.column_count == 3
    assert elapsed < 10, f"20k-row Parquet sanity load took {elapsed:.2f}s"
