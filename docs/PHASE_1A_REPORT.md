# HaraLens — Phase 1A report

## Summary

Phase 1A implements a reusable ingestion contract, validated hard resource limits,
typed failures, and bounded CSV ingestion independent of Streamlit. It returns a
pandas DataFrame plus exact counts and serializable run/source metadata. No Phase
1B or later functionality was implemented.

## Architecture decisions

- The request accepts bytes rather than a filesystem path. A future upload/storage
  boundary owns file access, while the adapter cannot traverse caller-supplied paths.
- `IngestionAdapter` is a typed Protocol. The CSV implementation is replaceable and
  future source adapters can share the request/result/error vocabulary.
- Pandas is the single Phase 1A table representation and a direct runtime dependency.
  Polars, DuckDB and additional table engines would add complexity without serving
  this bounded slice. `pandas-stubs` is development-only for strict type checking.
- Limits are validated immutable values. The CSV adapter checks bytes before decode,
  then validates structure, headers, columns and rows before DataFrame construction.
- CSV validation is deliberately two-pass: Python's strict CSV parser establishes
  structural safety and exact bounds; pandas creates the analysis-ready table.
- UTF-8 is deterministic. UTF-8 BOM is supported; guessing legacy encodings is not.
- Duplicate, empty and whitespace-only headers fail before pandas can silently rename
  them. Other valid names are preserved exactly. Blank physical lines are ignored,
  while quoted/all-missing data rows count as real rows.
- Materialized DataFrame row count, column count and header order must exactly match
  structural validation. A mismatch produces `IngestionConsistencyError` and no result.
- Filenames are display metadata only. Directory components are removed, control
  characters replaced and output length bounded across Windows/POSIX separators.
  Extensions are not trusted.
- Logs contain fixed events, safe source metadata, counts, failure codes and duration.
  They do not contain CSV rows or cell values.

## Validation results

| Check | Result |
| --- | --- |
| Full pytest suite | 63 passed, 0 failed, 0 skipped |
| Measured coverage | 99.70%: 299 statements, 1 missed; 30 branches, 0 partial |
| Ruff lint/security | Passed |
| Ruff format check | Passed |
| Strict mypy | Passed: 17 source files |
| Pre-commit config/hooks | Passed |
| Dependency compatibility | Passed: 71 installed packages |
| Package build | Source distribution and wheel built successfully |
| FastAPI smoke | HTTP 200 with expected HaraLens health JSON |
| Streamlit smoke | Health HTTP 200; root served HTML |
| Git whitespace | Passed; Windows LF/CRLF conversion notices only |
| Docker | Not run: Docker is not installed or available on PATH |

The test suite includes 50 new Phase 1A cases: 35 CSV behavior cases, ten ingestion
model cases, three settings cases, one logging case and one 20,000-row performance
sanity case. The latter completed inside a 10-second regression guard; it is not a
production throughput benchmark.
All 13 existing Phase 0 tests remain in the passing total.

Pytest continues to report the two existing upstream Starlette/AnyIO deprecation
warnings documented in the Phase 0 report. They do not represent test failures.

## Known limitations

- Input is caller-owned in-memory bytes; streaming and larger-than-memory ingestion
  are not implemented.
- Only comma-delimited UTF-8 CSV is supported. Dialect selection, delimiter inference
  and legacy encodings are not implemented.
- There is no Streamlit upload flow or ingestion API endpoint.
- Excel, Parquet, JSON, databases, REST APIs and Google Sheets are not implemented.
- Semantic type inference, profiling, quality checks, scoring, recommendations,
  persistence, authentication, ML, AI and reporting are not implemented.
- Resource limits bound encoded bytes, rows and columns. Memory and execution-time
  budgets remain future extensions.
- A semicolon/tab-delimited source can appear as valid single-column CSV because
  single-column CSV is valid. Dialect support requires an explicit contract change.

## Errors encountered and resolved

1. The first focused code check found long lines. Ruff formatting plus one manual
   message wrap resolved them.
2. Strict mypy identified missing pandas types. `pandas-stubs` was added as a
   development dependency and the lockfile updated; strict mypy then passed.
3. The initial focused suite passed all 31 selected tests but exited nonzero because
   repository-wide coverage included omitted Phase 0 modules. The authoritative full
   suite passed at 99.67%; no threshold was weakened.
4. Review found that filtering rows by nonempty cell content would mistake a quoted
   all-missing record for a blank line. The adapter now ignores only empty physical
   records and tests the all-missing case.
5. A final public-export edit introduced one import-order lint failure. The imports
   were sorted and Ruff plus pre-commit were rerun successfully.
6. The pre-freeze hardening audit found that the post-pandas invariant used a generic
   malformed-source error and that empty headers were rejected only indirectly after
   pandas renamed them. Dedicated consistency and invalid-column-name errors now make
   both policies explicit, with portable filename and invariant regression coverage.

## File inventory

### Created

- `docs/INGESTION.md`
- `docs/PHASE_1A_REPORT.md`
- `src/haralens/ingestion/__init__.py`
- `src/haralens/ingestion/contracts.py`
- `src/haralens/ingestion/csv.py`
- `src/haralens/ingestion/errors.py`
- `src/haralens/ingestion/models.py`
- `tests/performance/test_csv_ingestion_sanity.py`
- `tests/unit/test_csv_ingestion.py`
- `tests/unit/test_ingestion_models.py`

### Modified

- `.env.example`
- `README.md`
- `SECURITY.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT.md`
- `docs/ROADMAP.md`
- `pyproject.toml`
- `src/haralens/common/config.py`
- `src/haralens/common/logging.py`
- `tests/unit/test_config.py`
- `tests/unit/test_logging.py`
- `uv.lock`

No files were deleted.

## Next recommended task — not started

**Phase 1B — bounded Excel and Parquet ingestion using the established ingestion
contract.**
