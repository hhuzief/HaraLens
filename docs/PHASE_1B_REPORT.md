# HaraLens — Phase 1B report

## Phase 1B summary

Phase 1B extends the existing in-memory ingestion contract with bounded, deterministic
XLSX and Parquet adapters. Both return the same pandas-based `IngestionResult`, enforce
common header and post-materialization invariants, emit safe structured logs, and add
serializable format metadata. Existing CSV behavior remains covered and unchanged.

No Phase 1C semantic inference, profiling, UI upload, API ingestion endpoint, persistence,
quality scoring, ML, or AI behavior was implemented.

## Architecture decisions

- **Excel engine:** `openpyxl 3.1.5` in lazy read-only mode, with `defusedxml 0.7.1`
  installed for XML attack protection. Workbooks come from bytes and are never extracted.
- **Worksheet selection:** empty visible worksheets are ignored. One visible worksheet
  containing any loaded non-`None` value is selected automatically; multiple usable visible
  sheets require an exact `worksheet_name`. Hidden and very-hidden worksheets require
  explicit selection. Lazy probing shares the configured cell budget. Sheets are never combined.
- **XLSX headers:** valid strings remain exact; booleans, integers, finite floats, dates, and
  datetimes receive documented deterministic string forms. Invalid values fail, and duplicate
  checks catch both typed source duplicates and canonicalization collisions. Serializable
  metadata retains the accepted original header values.
- **Formula policy:** `data_only=False`, `keep_links=False`, and `keep_vba=False`. Formula
  text is returned as data. HaraLens never calculates formulas or substitutes cached values.
- **Merged-cell policy:** any merge crossing the selected header row is rejected. Merges
  below it produce the top-left value and missing values in the other merged positions.
- **Archive safety:** ZIP metadata and integrity are checked before workbook parsing, with
  configurable entry, expansion, compression-ratio, worksheet, and cell limits.
- **Parquet engine:** PyArrow 25 reads validated in-memory bytes. Footer metadata supplies
  dimensions, schema, and row groups before full materialization.
- **Nested-schema policy:** top-level nested Arrow types, including LIST, STRUCT, and MAP,
  are rejected with a typed error. Primitive, nullable, timestamp, and dictionary-encoded
  columns are accepted without Phase 1C classification.
- **Shared contract:** `worksheet_name` is an optional typed request field. Binary formats
  use `encoding=None`; format-specific metadata stays serializable. Shared helpers centralize
  filename sanitation, column validation, byte bounds, and DataFrame invariants.

## Security decisions

XLSX checks occur before `openpyxl`: source bytes, ZIP validity, required package members,
OOXML content type, duplicate/unsafe paths across POSIX and Windows separators, encryption,
declared uncompressed total, per-member compression ratio, macro indicators, and CRC. The
adapter rejects legacy OLE and macro-enabled workbooks and disables retained external links.

Parquet checks source bytes, both `PAR1` markers, footer length, metadata bytes, rows,
columns, row groups, column names, and nested types before reading the full table. PyArrow
also receives bounded Thrift parser settings and page-checksum verification. Conversion
ignores pandas metadata to prevent hidden index columns from changing the validated schema.

Logs contain source type, sanitized source name, source size, selected worksheet or row-group
count, dimensions, duration, and stable error codes. Tests verify that cell values are absent.

## Validation results

| Check | Result |
| --- | --- |
| Locked environment | Passed: 77 packages resolved and checked offline |
| Full pytest suite | 154 passed, 0 failed, 0 skipped |
| Measured coverage | 99.89%: 749 statements, 1 missed; 164 branches, 0 partial |
| Existing CSV suite | 35 CSV unit cases plus performance regression remained green |
| Ruff lint/security | Passed |
| Ruff format check | Passed: 49 files formatted |
| Strict mypy | Passed: 20 source files |
| Pre-commit | Both local Ruff hooks passed |
| Dependency compatibility | Passed: all 77 installed packages compatible |
| Package build | Source distribution and wheel built successfully |
| FastAPI smoke | HTTP 200 with expected HaraLens health JSON |
| Streamlit smoke | Health HTTP 200 and root served HTML; owned process stopped |
| Git whitespace | Passed; informational Windows LF/CRLF notices only |
| Docker | Not run: Docker is unavailable on PATH |

Pytest reports the same two upstream Starlette/AnyIO deprecation warnings as Phase 1A.
They are visible and unsuppressed.

## File inventory

### Created

- `docs/PHASE_1B_REPORT.md`
- `src/haralens/ingestion/_shared.py`
- `src/haralens/ingestion/parquet.py`
- `src/haralens/ingestion/xlsx.py`
- `tests/performance/test_binary_ingestion_sanity.py`
- `tests/unit/test_parquet_ingestion.py`
- `tests/unit/test_xlsx_ingestion.py`

### Modified

- `.env.example`
- `README.md`
- `SECURITY.md`
- `docs/ARCHITECTURE.md`
- `docs/DEVELOPMENT.md`
- `docs/INGESTION.md`
- `docs/ROADMAP.md`
- `pyproject.toml`
- `src/haralens/common/config.py`
- `src/haralens/ingestion/__init__.py`
- `src/haralens/ingestion/csv.py`
- `src/haralens/ingestion/errors.py`
- `src/haralens/ingestion/models.py`
- `tests/unit/test_config.py`
- `tests/unit/test_ingestion_models.py`
- `uv.lock`

No files were deleted.

## Known limitations

- Inputs and results are in memory. File, archive, metadata, row, column, and cell limits do
  not provide a strict process-memory or execution-time budget.
- Only macro-free `.xlsx` content is supported. `.xls`, `.xlsm`, templates, formula
  calculation, external-link retrieval, and automatic multi-sheet combination are absent.
- XLSX header canonicalization is deliberately limited to strings, booleans, integers,
  finite floats, dates, and datetimes. Leading/trailing empty worksheet rows are ignored;
  internal empty rows remain table rows.
- Nested Parquet schemas are rejected. Encrypted Parquet and larger-than-memory streaming
  are not implemented.
- No upload UI or ingestion HTTP endpoint exists.

## Errors encountered

1. An initial broad inspection emitted too much output and included two nonexistent paths.
   Reads were narrowed and corrected to `src/haralens/common/config.py` and `docker/Dockerfile`.
2. The first dependency command was blocked from PyPI by the sandbox. The approved network
   retry added and locked the required packages successfully.
3. Strict mypy found missing third-party type metadata. Development-only `types-openpyxl`,
   `types-defusedxml`, and `pyarrow-stubs` dependencies resolved it without weakening mypy.
4. The first focused test collection exposed a bracket typo. After correction, three tests
   exposed merged-header precedence, malformed-footer precedence, and a recursive monkeypatch.
   Each issue was fixed and regression-tested.
5. A combined delete/add documentation patch was rejected by the patch tool. Sequential
   delete and add operations succeeded without data loss.
6. Docker remains unavailable. The two upstream test deprecation warnings remain unresolved.

## Commands and outcomes

The authoritative final commands were:

| Command | Outcome |
| --- | --- |
| `uv sync --locked --offline` | Passed; 77 packages checked |
| `uv run --locked pytest` | Passed; 154 tests, 99.89% coverage |
| `uv run --locked ruff check .` | Passed |
| `uv run --locked ruff format --check .` | Passed |
| `uv run --locked mypy` | Passed |
| `uv run --locked pre-commit run --all-files` | Passed |
| `uv pip check` | Passed |
| `uv build --offline` | Passed; sdist and wheel built |
| `uv run --locked python scripts/smoke.py` | Passed; FastAPI and Streamlit |
| `git diff --check` | Passed |
| Docker availability check | Docker unavailable |

Inspection used `git status`, `git log`, `rg --files`, `rg`, and targeted `Get-Content`
commands. Implementation edits used `apply_patch`. Focused pytest, Ruff, formatting, and
mypy commands were run throughout; their intermediate failures and resolutions are listed
above. Official openpyxl, PyArrow, and Python ZIP documentation was consulted for parser,
formula, metadata, and archive behavior.

## Next recommended task — not started

**Phase 1C — semantic type inference.**
