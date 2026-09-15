# Bounded ingestion

## Scope and contract

Phase 1B provides independent adapters for comma-delimited UTF-8 CSV, macro-free
`.xlsx` workbooks and flat Parquet files. The package has no FastAPI endpoint or
Streamlit upload flow. JSON, databases, URLs, `.xls`, `.xlsm`, semantic inference,
profiling and cleanup remain outside the implemented scope.

`IngestionRequest` carries caller-owned bytes, an untrusted display filename, hard
`ResourceLimits`, and an optional exact `worksheet_name`. Every adapter returns an
`IngestionResult` with a pandas DataFrame, exact dimensions, and serializable common
plus format-specific metadata. Typed `IngestionError` subclasses expose stable codes
and safe messages.

CSV and Parquet require text column names. XLSX accepts the safe scalar header policy
defined below. Every format rejects duplicate, empty, and whitespace-only names before
pandas can invent or mutate them. Valid strings are preserved exactly. After
materialization, the DataFrame row count, column count, and column order must match the
validated structure or `IngestionConsistencyError` is raised.

## CSV policy

- CSV remains strict comma-delimited UTF-8. A UTF-8 BOM is accepted. Legacy encoding
  guesses, delimiter inference, and malformed-row skipping are not implemented.
- The byte, row, and column limits are checked before DataFrame construction. Blank
  physical lines are ignored; a quoted all-missing record remains a data row.
- Formula-like strings remain strings and are never evaluated.
- See the [Phase 1A report](PHASE_1A_REPORT.md) for the complete frozen CSV behavior.

## XLSX policy

### Workbook and worksheet selection

- Only macro-free OOXML `.xlsx` content is supported. The adapter recognizes the ZIP
  package and required XLSX content type rather than trusting the filename. Legacy OLE
  `.xls`, macro-enabled `.xlsm`, arbitrary ZIP files, and malformed packages fail with
  typed errors.
- A **usable worksheet** is visible and contains at least one cell whose value loaded by
  `openpyxl` is not `None`. Whitespace strings, formulas, Excel errors, and other present
  values make a sheet usable for selection; header validation still decides whether that
  content is a valid table.
- With no requested name, exactly one usable worksheet is selected. Empty visible sheets
  are ignored. Multiple usable visible worksheets require an explicit exact name. If none
  exist, ingestion fails with `NoUsableWorksheetError`.
- Hidden and very-hidden worksheets are not probed or selected automatically but may be
  selected explicitly. Empty/header-only validation then applies normally. Sheets are
  never combined.
- Auto-selection uses lazy row iteration, stops probing each sheet at its first present
  value, and shares `max_xlsx_cells` across all probed sheets. The selected sheet is then
  read under the same per-sheet cell limit. Workbook ZIP expansion and sheet-count limits
  bound the surrounding work.
- The first row containing a value is the header. Leading empty rows and trailing empty
  rows are ignored. Empty rows between data rows remain data rows.

### XLSX header canonicalization

- Valid string headers, including formula text, are preserved exactly.
- Booleans become uppercase `TRUE` or `FALSE`.
- Integers use decimal `str(value)` form. Finite floats use Python's deterministic
  shortest round-trip `repr(value)` form.
- Dates and datetimes use ISO 8601 via `isoformat()`.
- Blank cells, whitespace-only strings, non-finite floats, Excel error cells, and other
  scalar/object types are rejected with one-based invalid positions.
- Identical typed source headers are checked before naming. Canonical names are checked
  again, so pairs such as numeric `2024` and text `"2024"` fail rather than being renamed.
- `ExcelFormatMetadata.original_column_headers` retains the accepted original typed values
  in serializable form; DataFrame columns always use the canonical string names.

### Security and representation

- ZIP metadata is inspected before `openpyxl`: member count, duplicate normalized paths, traversal
  paths across both separator styles, encryption flags, declared uncompressed total,
  per-entry compression ratio, required members, content type, and CRC integrity.
  Nothing is extracted to disk.
- `defusedxml` protects the XML parser against entity expansion attacks. `openpyxl`
  uses lazy read-only mode, ignores preserved external workbook links, does not retain
  VBA, and is always closed.
- Workbooks are opened with `data_only=False`. Formula text such as `=SUM(A1:A2)` is
  returned as text; HaraLens never calculates it or substitutes a cached result.
- A merged range intersecting the chosen header row is rejected because it makes column
  identity ambiguous. Merges below the header are represented deterministically as the
  top-left value plus missing values for the other merged cells.
- Dates, booleans, numbers, and strings retain the physical Python/pandas types produced
  by `openpyxl`. This is physical loading, not semantic type inference.

## Parquet policy

- The adapter requires Parquet `PAR1` container markers and validates the declared
  footer length and metadata-size limit before invoking PyArrow.
- `pyarrow.parquet.ParquetFile` supplies row count, top-level schema, and row-group
  count before materialization. Row, column, and row-group limits are therefore checked
  before reading the full table. Thrift parser string/container limits and page checksum
  verification provide additional parser bounds and integrity checks.
- Primitive physical types, timestamps, nullable fields, and dictionary-encoded values
  are supported. Any top-level LIST, STRUCT, MAP, or other nested Arrow type is rejected
  with `UnsupportedParquetSchemaError`; nested values are never stringified.
- Pandas metadata is ignored during conversion so index metadata cannot add or reorder
  columns. The validated Arrow schema order is the required DataFrame order.
- A schema with no columns is an empty source. A schema with columns and zero rows is a
  no-data-rows failure, matching the CSV header-only rule.

## Default limits

| Environment variable | Default | Meaning |
| --- | ---: | --- |
| `HARALENS_INGESTION_MAX_SOURCE_BYTES` | 10,485,760 | Bytes for every source format |
| `HARALENS_INGESTION_MAX_ROWS` | 100,000 | Data rows, excluding a CSV/XLSX header |
| `HARALENS_INGESTION_MAX_COLUMNS` | 1,000 | Top-level table columns |
| `HARALENS_INGESTION_MAX_XLSX_ARCHIVE_ENTRIES` | 1,000 | ZIP member count |
| `HARALENS_INGESTION_MAX_XLSX_UNCOMPRESSED_BYTES` | 104,857,600 | Declared ZIP expansion total |
| `HARALENS_INGESTION_MAX_XLSX_COMPRESSION_RATIO` | 200.0 | Maximum ratio for one ZIP member |
| `HARALENS_INGESTION_MAX_XLSX_WORKSHEETS` | 100 | Worksheet count |
| `HARALENS_INGESTION_MAX_XLSX_CELLS` | 1,000,000 | Auto-selection probe, scanned sheet, and dense table cells |
| `HARALENS_INGESTION_MAX_PARQUET_METADATA_BYTES` | 8,388,608 | Declared footer metadata bytes |
| `HARALENS_INGESTION_MAX_PARQUET_ROW_GROUPS` | 1,000 | Row groups |

Limits are positive and inclusive. A source exactly at a limit is accepted. The XLSX
compression-ratio limit is a positive float; the others are positive integers.

```python
from haralens.common.config import Settings
from haralens.ingestion import IngestionRequest, ParquetIngestionAdapter

request = IngestionRequest(
    content=parquet_bytes,
    source_name="example.parquet",
    limits=Settings().ingestion_limits,
)
result = ParquetIngestionAdapter().ingest(request)
```

## Limits of the limits

Inputs are in-memory bytes. Source-size, container, metadata, row, column, and cell
limits reduce predictable abuse, but they do not create a strict process-memory or CPU
budget. In particular, Parquet compression and type conversion can require much more
memory than the encoded source. Larger-than-memory streaming, timeouts, and worker
isolation remain future hardening work.

CI sanity tests load 2,000 XLSX rows and 20,000 Parquet rows with deliberately generous
guards. They detect catastrophic regressions and are not throughput guarantees.
