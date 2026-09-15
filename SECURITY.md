# Security

The application exposes only process health and a static application shell.
Authentication, authorization, uploads, database access, and tenant isolation are
not implemented.
Use local loopback bindings; this foundation is not a production SaaS deployment.

Do not commit `.env`, tokens, datasets, or Streamlit secrets. Application logs use
fixed event names and must never include credentials or raw data. The JSON formatter
does not sanitize arbitrary messages; callers are responsible for safe event content.
Uvicorn access logging is disabled in documented commands to avoid query-string logs.

Future adapters must validate identity, enforce tenant ownership on every operation,
and include cross-tenant tests before release. Domain organization IDs and Protocols
are contracts, not implemented authorization controls.

Report vulnerabilities privately to the repository maintainer through GitHub private
vulnerability reporting if enabled. Do not post sensitive evidence in public issues.

Phase 1A CSV ingestion accepts bytes supplied by a caller; it never opens a supplied
filename or path. Display filenames are reduced to a basename, control characters are
replaced, and length is bounded. The adapter strictly accepts UTF-8, rejects NUL bytes,
checks hard byte/row/column limits, and rejects malformed rows and duplicate headers.
CSV cells are treated as data and are never evaluated. Raw content and cell values
must not be logged. Spreadsheet formula safety during later export is outside this
phase and must be handled by the export boundary.

Empty and whitespace-only headers are rejected before pandas can synthesize names.
Post-materialization dimensions and headers must match structural validation or the
adapter raises a typed consistency error and returns no table. Filename sanitization
handles both Windows and POSIX separators regardless of the server operating system.

Phase 1B applies the same untrusted-name and safe-logging rules to XLSX and Parquet.
XLSX files are ZIP packages, so HaraLens rejects unsafe or duplicate normalized paths,
encrypted members, excessive entry/uncompressed-size/compression-ratio values, invalid
content types, integrity failures, legacy OLE workbooks, and macro-enabled packages before
`openpyxl` loads a workbook. Files are never extracted. `defusedxml` protects XML parsing;
external workbook links are not retained; formulas are returned as text and never run.
Every metadata-based archive guard runs before member decompression, CRC verification, and
workbook parsing. Automatic sheet discovery is lazy and shares the configured cell budget.

Parquet magic and footer length are checked before PyArrow. Footer metadata is bounded and
used to reject excessive rows, columns, and row groups before full materialization. Nested
schemas are rejected rather than converted to strings. These controls reduce decompression
and parser risk but do not guarantee a strict memory bound: Parquet decoding and pandas
conversion can expand beyond source bytes. Worker isolation and process-level budgets are
future production controls.
