# HaraLens v0.1 — Gate 2 Product Verification Report

## Executive summary

Gate 2 adds a working Streamlit upload-to-results workflow around the existing deterministic
engine. The application supports CSV, XLSX, and Parquet through hardened ingestion, handles Excel
worksheet selection, displays engine-derived overview/quality/profile/recommendation results, and
keeps analysis state session-scoped.

## Application architecture

`haralens.application.analyze_uploaded_dataset` is the only orchestration
path: upload → bounded adapter → semantic inference → profiling → quality runner → health scorer
→ recommendations → typed `AnalysisResult` → Streamlit rendering.

## Files/pages created

- `src/haralens/application/analysis.py`
- `src/haralens/application/__init__.py`
- Home, Analyze, and Methodology/About views in `apps/streamlit/app.py`
- `tests/unit/test_analysis_service.py`
- `docs/GATE_2_PRODUCT_WORKFLOW.md`
- this report

## Upload and result experience

Home communicates product positioning, supported formats, limits, privacy scope, and methodology
disclaimer. Analyze accepts CSV/XLSX/Parquet, runs the hardened adapters, reports meaningful
stages, and renders Overview, Quality, Columns, and Recommendations tabs. The score and six
dimensions come directly from `HealthScoreResult`; `None` remains Not evaluated.

## Error/session/privacy behavior

Typed ingestion failures are shown as safe messages. Multi-sheet workbooks return the available
worksheet choices. Partial failures never replace the previous result. Reset removes result,
identity, worksheet, and error state. No module-level dataset, shared temporary upload, or global
user-data cache was introduced. Raw data is not displayed by default and raw bytes are not retained
in `AnalysisResult`.

## Manual acceptance results

| Scenario | Result | Notes |
|---|---|---|
| Clean CSV | Passed | Score 100.0, no findings, useful profile and empty recommendation state |
| Problematic CSV | Passed | Multiple findings and recommendations from engine output |
| Single-sheet XLSX | Passed | Explicit worksheet supplied to hardened adapter |
| Multi-sheet XLSX | Passed | Typed worksheet-selection requirement returned safe worksheet names |
| Parquet | Passed | Full service pipeline completed |
| Invalid upload | Passed | Typed failure rendered without traceback |
| Reset / second upload | Implemented and covered by session reset path | Result and upload identity are cleared before rerun |

## Validation

The focused Gate 2 tests pass: **6 passed**. The complete suite contains **454 tests**. In the
current offline editable environment, **452 passed and 2 FastAPI tests fail** because the local
editable distribution reports a `None` package version; the same suite was green at the Gate 2
baseline before this environment issue surfaced. The run still reports
96.77% combined coverage on that run. Ruff, format, strict mypy, Streamlit smoke, and dependency
compatibility pass. Pre-commit was attempted but its hook environment was unavailable locally
without network access. Package build remains blocked locally by the unavailable offline Hatchling
cache. Docker is unavailable on the host.

## Known limitations

The application does not add persistence, authentication, FastAPI product endpoints, reporting,
PDF export, or Gate 3 functionality. Streamlit's native runtime remains the presentation host.
