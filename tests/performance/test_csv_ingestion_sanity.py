import time

from haralens.ingestion.csv import CsvIngestionAdapter
from haralens.ingestion.models import IngestionRequest, ResourceLimits


def test_20k_row_csv_completes_within_sanity_budget() -> None:
    """Catch pathological regressions; this is not a large-scale benchmark."""
    rows = ["id,category,value"]
    rows.extend(f"{index},group-{index % 10},{index * 2}" for index in range(20_000))
    content = ("\n".join(rows) + "\n").encode()
    request = IngestionRequest(
        content=content,
        source_name="synthetic-20k.csv",
        limits=ResourceLimits(
            max_source_bytes=len(content),
            max_rows=20_000,
            max_columns=3,
        ),
    )

    started = time.perf_counter()
    result = CsvIngestionAdapter().ingest(request)
    elapsed = time.perf_counter() - started

    assert result.row_count == 20_000
    assert result.column_count == 3
    assert elapsed < 10, f"20k-row sanity load took {elapsed:.2f}s"
