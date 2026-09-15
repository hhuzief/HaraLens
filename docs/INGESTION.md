# CSV ingestion

## Scope

Phase 1A implements an ingestion contract and one adapter for caller-owned CSV bytes.
It is independent of FastAPI and Streamlit. There is no upload endpoint or UI yet.
Excel, Parquet, JSON, databases, URLs, semantic inference, profiling and cleanup are
not implemented.

`IngestionAdapter` defines the reusable operation. `IngestionRequest` contains bytes,
an untrusted display filename and hard `ResourceLimits`. `IngestionResult` contains a
pandas DataFrame, exact row/column counts and serializable `IngestionMetadata`.
Typed `IngestionError` subclasses expose stable codes and safe messages.

## CSV policy

- Only comma-delimited UTF-8 text is supported. UTF-8 BOM is accepted and reported
  as `utf-8-sig`. No probabilistic encoding detection or legacy-codepage fallback.
- The adapter checks source bytes before decoding. It validates CSV structure and
  row/column limits before creating the pandas DataFrame.
- Blank physical lines are ignored consistently, but malformed records are never
  skipped. Exceeding a hard limit fails the entire ingestion; no sampling/truncation.
- Zero-byte, blank-only and header-only sources have distinct typed failures.
- Duplicate, empty and whitespace-only column names are rejected before pandas can
  rename them. Error positions are one-based. Other valid column names, including
  leading or trailing whitespace around nonempty names, are preserved exactly;
  ingestion performs no destructive normalization.
- Filename extensions are metadata, not proof of format. The adapter validates UTF-8
  text and CSV structure. It never opens or executes a supplied filename/path.
- NUL-bearing content is rejected as implausible CSV text. CSV formula-like strings
  remain ordinary cell values and are never evaluated.
- After pandas materializes the table, its row count, column count and exact header
  sequence must match structural validation. Any mismatch raises the typed
  `IngestionConsistencyError`; no table is returned.

The fixed comma separator intentionally keeps Phase 1A deterministic. A semicolon or
tab-delimited file may look like a single-column CSV because single-column CSV is valid;
delimiter selection and dialect support require an explicit later contract change.

## Default limits

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `HARALENS_INGESTION_MAX_SOURCE_BYTES` | 10,485,760 | 10 MiB encoded source |
| `HARALENS_INGESTION_MAX_ROWS` | 100,000 | Data rows, excluding header |
| `HARALENS_INGESTION_MAX_COLUMNS` | 1,000 | Header columns |

All limits are positive integers and inclusive: a source exactly at a limit is
accepted. Application boundaries should construct requests using
`Settings().ingestion_limits`. Tests may inject smaller limits directly.

```python
from haralens.common.config import Settings
from haralens.ingestion import CsvIngestionAdapter, IngestionRequest

request = IngestionRequest(
    content=b"name,value\nA,1\n",
    source_name="example.csv",
    limits=Settings().ingestion_limits,
)
result = CsvIngestionAdapter().ingest(request)
```

## Performance and limitations

The adapter validates once with Python's strict CSV parser and then parses with
pandas. This deliberate two-pass design catches structural problems before returning
a table, at the cost of extra CPU and a decoded in-memory copy. The 10 MiB default
bounds that cost. Phase 1A accepts in-memory bytes; streaming sources and memory/time
budgets remain future work.

The sanity test ingests 20,000 rows and requires completion within 10 seconds. It can
catch gross algorithmic regressions on CI-class hardware. It does not establish
larger-than-memory behavior, production throughput or a formal performance guarantee.
