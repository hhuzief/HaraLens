# HaraLens — Phase 1B pre-freeze hardening audit

## Scope

This audit covers worksheet auto-selection, XLSX header policy, security-relevant branch
coverage, and XLSX archive validation order. It remains within Phase 1B. CSV semantics,
Parquet features, API/UI scope, and Phase 1C semantic inference were not expanded.

The audit began from 117 passing tests and 95.52% measured coverage.

## 1. XLSX worksheet auto-selection

### Finding

The prior implementation equated visible sheets with selectable sheets. Consequently, an
empty visible sheet could force a selection even when exactly one other visible sheet held
data. This was deterministic but needlessly obstructive.

### Final policy

A worksheet is **usable for automatic selection** when both conditions hold:

1. its state is `visible`; and
2. lazy `openpyxl` iteration finds at least one cell whose loaded value is not `None`.

Whitespace strings, formula text, Excel errors, and other present scalar values establish
usability; table/header validation may still reject that sheet after selection. Hidden and
very-hidden sheets are not probed automatically. An explicitly named hidden, very-hidden,
empty, or header-only worksheet continues through the normal selected-sheet validation.

The probe resets untrusted declared dimensions, iterates lazily, stops at the first value in
each visible sheet, and shares `max_xlsx_cells` across all candidate sheets. ZIP expansion
and worksheet-count limits remain in force. It does not create DataFrames or combine sheets.

### Regression coverage

- one populated visible sheet plus one empty visible sheet
- one populated visible sheet plus three empty visible sheets
- two populated visible sheets requiring selection
- all visible sheets empty
- empty visible sheet plus populated hidden sheet
- explicit hidden, very-hidden, and empty-sheet selection
- cell-budget exhaustion during automatic probing
- chart-only workbook with no tabular worksheet

## 2. XLSX non-text header policy

### Finding

Rejecting every non-string header was stricter than the common HaraLens string-column
contract required. Excel has a bounded set of scalar physical values that can be converted
without guessing semantic meaning.

### Final policy

| Loaded XLSX header | Canonical DataFrame column |
| --- | --- |
| Valid string or formula text | Preserved exactly |
| Boolean | `TRUE` or `FALSE` |
| Integer | Decimal `str(value)` |
| Finite float | Shortest round-trip `repr(value)` |
| Date | ISO 8601 `date.isoformat()` |
| Datetime | ISO 8601 `datetime.isoformat()` |

Blank cells, whitespace-only strings, non-finite floats, Excel error cells, times, and other
objects fail with `InvalidColumnNamesError` and one-based positions. Headers are checked for
identical typed source values before the canonical names are checked again. Collisions such
as numeric `2024` with text `"2024"`, boolean `TRUE` with text `"TRUE"`, or float `1.5`
with text `"1.5"` raise `DuplicateColumnsError`; pandas never chooses a replacement.

Accepted source values are retained in serializable
`ExcelFormatMetadata.original_column_headers`. This records a transformation without adding
semantic classification.

### Regression coverage

Tests cover strings, integers, finite/non-finite floats, dates, datetimes, booleans, blanks,
whitespace, formula headers, Excel error values, unsupported time values, typed duplicates,
canonicalization collisions, end-to-end DataFrame names, and metadata serialization.

## 3. Security coverage audit

The audit added deterministic coverage for:

- exact entry-count and declared expanded-size guards
- high and impossible per-member compression ratios
- POSIX, Windows, mixed/internal, absolute, and drive-qualified traversal names
- duplicate normalized/case-folded archive paths
- encrypted central-directory flags
- missing required OOXML members and wrong workbook content types
- content-type and `vbaProject.bin` macro indicators
- legacy OLE input
- empty members and deterministic CRC corruption
- malformed workbook and merged-range XML
- worksheet-count, selection-probe, scanned-cell, dense-cell, row, and column limits
- hidden/very-hidden/empty/chart-only selection
- merged-header, formula, and materialization-invariant behavior

Parquet already had complete adapter statement and branch coverage for invalid magic/footer,
metadata/row/column/row-group limits, malformed metadata translation, LIST/STRUCT/MAP
rejection, invalid/duplicate names, materialization invariants, schema ordering, and parser
read failures. Constructing an actual checksum-bearing Parquet page with deterministic
checksum corruption was not added: the existing reader is configured with
`page_checksum_verification=True`, and parser/read failure translation is covered without
binding tests to private PyArrow page-layout details.

### Remaining coverage

Final coverage is **99.89%**: 749 statements, one missed; 164 branches, all covered.

The sole missed statement is `src/haralens/ingestion/csv.py:126`, a defensive
`StopIteration` translation after nonblank text has already passed `text.strip()` and the
strict CSV reader has filtered only empty physical rows. Normal inputs reach the earlier
blank-source failures or produce a header. Forcing this line would require mocking the
standard-library parser into contradicting that established state. The user-visible empty
CSV behavior is already covered, so the line is intentionally retained and unforced.

All XLSX and Parquet adapter statements and branches are covered. No security or integrity
branch remains untested.

## 4. XLSX archive validation order

The final order is:

1. enforce encoded source-byte and zero-byte/legacy-OLE checks;
2. open the ZIP and read its central directory;
3. enforce entry count;
4. reject duplicate normalized paths, traversal paths, and encrypted flags;
5. enforce total declared uncompressed bytes;
6. enforce positive compressed sizes and per-member compression ratios;
7. require the OOXML workbook members;
8. decompress only `[Content_Types].xml` to validate XLSX/macro type;
9. run `ZipFile.testzip()` to decompress members and verify CRC;
10. invoke `openpyxl` only after every container guard succeeds.

The regression test patches member reads, CRC verification, and `openpyxl.load_workbook` to
fail immediately, then triggers the compression-ratio guard. The guard wins, proving those
decompression/parsing operations are not reached first. CRC corruption also has an
end-to-end typed-failure test.

## Exact changes

- Added bounded usable-sheet probing and deterministic empty-sheet exclusion.
- Added scalar XLSX header canonicalization, typed duplicate/collision checks, and original
  header metadata.
- Added normalized archive-path collision detection and rejection of internal `..` segments.
- Added `TypeError` translation for malformed `openpyxl` structures discovered by testing.
- Expanded XLSX policy, security, and integrity tests from 24 to 61 executed cases.
- Updated ingestion, security, and Phase 1B documentation.

## Final validation

| Check | Result |
| --- | --- |
| Full pytest with branch coverage | 154 passed, 0 failed, 0 skipped |
| Coverage | 99.89%; 749 statements, 1 missed; 164/164 branches covered |
| Detailed missed-line report | Generated and classified above |
| Ruff lint/security | Passed |
| Ruff format check | Passed: 49 files already formatted |
| Strict mypy | Passed: 20 source files |
| Pre-commit | Both local Ruff hooks passed |
| Dependency compatibility | All 77 installed packages compatible |
| Package build | Source distribution and wheel built successfully |
| FastAPI smoke | HTTP 200 with expected HaraLens health JSON |
| Streamlit smoke | Health HTTP 200 and root served HTML |
| `git diff --check` | Passed; informational Windows LF/CRLF notices only |
| Docker | Unavailable on PATH; not treated as a Phase 1B failure |

Pytest continues to show two unsuppressed upstream Starlette/AnyIO deprecation warnings.

## File inventory for this audit

### Created

- `docs/PHASE_1B_PRE_FREEZE_AUDIT.md`

### Modified

- `SECURITY.md`
- `docs/INGESTION.md`
- `docs/PHASE_1B_REPORT.md`
- `src/haralens/ingestion/errors.py`
- `src/haralens/ingestion/models.py`
- `src/haralens/ingestion/xlsx.py`
- `tests/unit/test_xlsx_ingestion.py`

No files were deleted. Dependencies and `uv.lock` were unchanged by this audit.

## Known limitations

- Ingestion remains in memory; existing bounds do not provide a strict process memory or
  execution-time budget.
- XLSX canonicalization deliberately excludes Excel errors, non-finite floats, time-only
  values, and arbitrary objects.
- A whitespace-only or otherwise invalid visible sheet is usable for selection because it
  contains a value; it then fails explicit header validation. Selection does not guess
  analytical validity.
- Nested and encrypted Parquet, `.xls`, `.xlsm`, formula calculation, upload UI, and an
  ingestion API remain outside Phase 1B.

## Errors encountered

The security fixtures revealed an untyped `openpyxl` `TypeError` for malformed merged-range
XML. The adapter now translates it to `MalformedWorkbookError`. No unresolved implementation
errors remain. Docker is unavailable, and the two upstream test warnings remain visible.

## Next task — not started

**Phase 1C — semantic type inference.**
