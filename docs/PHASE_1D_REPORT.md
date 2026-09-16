# HaraLens - Phase 1D verification report

## Summary

Phase 1D implements a reusable, deterministic, semantic-aware dataset and column profiling
engine. It accepts a table and its matching Phase 1C semantic result and returns immutable,
versioned, JSON-serializable descriptive profiles. It adds no API or Streamlit workflow and
does not implement quality judgments, scoring, recommendations, persistence, advanced
statistics, ML, reporting, authentication, or AI.

The service scans every row within an explicit resource envelope. It verifies semantic/table
shape, order, dtype, null-count, and distinct-count consistency before computation. Profile
results contain no run timestamp or duration, so identical inputs and configuration produce
identical serialized output.

## Models and behavior

`DatasetProfile` contains a `DatasetSummary`, ordered `ColumnProfile` items, configuration,
run metadata, version information, and typed warnings.

Dataset facts include exact dimensions, memory, missing cells, repeated duplicate rows,
effective semantic distribution, and empty/constant/identifier column counts. Column facts
include completeness, cardinality, memory, physical dtype, semantic meaning, and confidence.

Specialized models are:

- `NumericStatistics`: finite/non-finite counts, sign/zero counts, extrema, mean, median,
  variance, standard deviation, quartiles, IQR, skewness, and kurtosis;
- `CategoricalStatistics`: deterministic bounded frequencies, mode, remainder count, and
  Shannon entropy;
- `DatetimeStatistics`: parsed/unparsed/ambiguous counts, awareness state, range, and span;
- `TextStatistics`: rendered length distribution and empty/whitespace-only counts.

No model contains status, severity, health, failure, outlier, rarity, remediation, or score
fields. Operational failure warnings only describe whether a statistic could be computed.

## Numerical and datetime policy

Finite numeric aggregates exclude and separately count positive/negative infinity and
non-numeric values. Undefined or non-finite outputs become `null`, preventing invalid JSON
numbers. Scale-normalized calculations reduce overflow risk for large finite values. The
default uses sample variance/standard deviation (`ddof=1`) and linear quartiles; both are
configuration values embedded in the result.

Datetime parsing accepts native/Python calendar values and the narrow Phase 1C ISO/slash
surface. Ambiguous slash dates are counted and omitted from ranges instead of choosing a
locale. Aware values compare in UTC. Mixed naive/aware values withhold a range rather than
inventing a timezone.

## Resource and privacy policy

Defaults cap exact work at 100,000 rows, 1,000 columns, and 10,000,000 cells. Category output
is limited to ten values and 200 displayed characters per string. Limits are strict and
configurable; inputs beyond them fail instead of sampling or truncating computation.

Free-text and identifier profiles contain lengths only. Category values may appear in bounded
frequency output because those values are the described categories. No raw values or raw
exception messages enter warnings. No profiling code logs data.

## Tests added

The Phase 1D suite adds deterministic unit and bounded performance coverage for:

- dataset dimensions, deep memory, missing cells, duplicates, and empty shapes;
- numeric quartiles, sample/population variance, signs, zeros, infinities, undefined moments,
  large finite values, and JSON-safe output;
- stable tied frequencies, bounded top values, typed scalar values, truncation, mode, and
  entropy;
- Boolean, native datetime, ambiguous dates, mixed timezone awareness, text/identifier
  privacy, empty, constant, and user-overridden semantic columns;
- JSON round trips, immutability, repeatability, no input mutation, duplicate labels,
  ingestion-result input, stale/mismatched semantic profiles, resource limits, safe
  pathological values, and isolated statistic failures;
- an exact representative 100,000-row profile.

All pre-Phase-1D tests remain unchanged.

## Validation results

| Check | Result |
| --- | --- |
| Baseline full pytest with branch coverage | Passed: 302 tests, 99.93% coverage |
| Final full pytest with branch coverage | Passed: 390 tests, 98.96% combined coverage |
| Overall statement / branch coverage | 99.06% (1,687/1,703) / 98.56% (410/416) |
| Profiling statement / branch coverage | 96.77% (449/464) / 95.45% (126/132) |
| Ruff lint/security | Passed |
| Ruff format check | Passed: 72 files formatted |
| Strict mypy | Passed: 30 source files |
| Pre-commit | Passed with workspace-local cache |
| Dependency compatibility | Passed: all 77 installed packages compatible |
| Package build | Source distribution and wheel built successfully |
| FastAPI and Streamlit smoke checks | Passed with HTTP 200 responses |
| `git diff --check` | Passed; line-ending notices are informational |
| Docker | CLI unavailable locally; prior GitHub Actions were green |

The baseline and current test runs report two unchanged upstream Starlette/AnyIO deprecation
warnings.

## Files

### Created

- `docs/PROFILING.md`
- `docs/PHASE_1D_REPORT.md`
- `docs/PHASE_1D_PRE_FREEZE_AUDIT.md`
- `src/haralens/profiling/__init__.py`
- `src/haralens/profiling/config.py`
- `src/haralens/profiling/errors.py`
- `src/haralens/profiling/models.py`
- `src/haralens/profiling/service.py`
- `tests/unit/test_profiling.py`
- `tests/unit/test_profiling_hardening.py`
- `tests/performance/test_profiling_sanity.py`

### Modified

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

No files were deleted. Ingestion, semantic inference, application entry points, dependencies,
`pyproject.toml`, and `uv.lock` were not changed.

## Implementation issues found and resolved

- A focused performance assertion initially assumed 10,000 distinct rows, but the combined
  10,000-value amount, 12-value region, and two-value Boolean cycles repeat every 30,000 rows.
  The exact duplicate count is therefore 70,000; the fixture expectation was corrected.
- A first focused pytest command covered only the new tests while the project-wide coverage
  gate still measured every package. The tests themselves passed apart from the fixture
  expectation above; the authoritative coverage command is the full repository suite.
- Numerical review found that directly summing multiple near-maximum finite floats could
  overflow. Mean and moment calculations now operate on scale-normalized values, with a
  regression test for `1e308` inputs.
- The pre-freeze audit found that quantile interpolation still used unscaled endpoints and
  that a rendered category key could merge sufficiently long distinct strings. Quantiles/IQR
  now use normalized values, while category identity uses complete typed values independently
  of bounded display rendering.

No implementation issue is currently unresolved.

## Commands and outcomes

The implementation used repository-local uv and pre-commit caches.

| Command | Outcome |
| --- | --- |
| `git status --short`, branch/log and repository file inspection | Clean `main` at `688ca78`; Phase 1A-1C sources and reports present |
| Read product, architecture, roadmap, ingestion, semantic, Phase 1A-1C reports, models, configuration, tests, and `pyproject.toml` | Completed before modification |
| `uv run --locked pytest` (baseline) | Passed: 302 tests, 99.93% coverage |
| `uv run --locked ruff check .` (baseline) | Passed |
| `uv run --locked ruff format --check .` (baseline) | Passed |
| `uv run --locked mypy src tests` | Reported 16 pre-existing test-fixture typing errors; this is outside configured mypy scope |
| `uv run --locked mypy` (configured strict scope) | Passed: 25 source files at baseline |
| `uv run --locked pre-commit run --all-files` (baseline) | Passed |
| `uv pip check` (baseline) | Passed: 77 compatible packages |
| `uv build --offline` (baseline) | Built sdist and wheel |
| `uv run --locked python scripts/smoke.py` (baseline) | FastAPI and Streamlit passed; owned processes stopped |
| `git diff --check` (baseline) | Passed |
| `docker --version` | Could not run: Docker CLI is not installed |
| Focused Phase 1D pytest | First run found the duplicate-fixture expectation above; corrected |
| Focused Phase 1D pytest after corrections | Passed; expanded to 44 unit tests |
| Pre-freeze profiling hardening pytest | Passed: 43 audit tests |
| Detailed profiling-only coverage | 88 tests; 96.77% statements, 95.45% branches |
| Focused Ruff and strict mypy during implementation | Passed after formatting two long test lines |
| Final complete validation suite | Passed; results recorded above |

## Known limitations

- Exact profiling is intentionally bounded and can still be material near configured maxima.
- Deep pandas memory accounting is an estimate for some Python objects.
- A semantic/table consistency check detects structural and count changes, but cannot detect a
  same-shape value permutation that preserves dtype, null count, and distinct count.
- Mixed naive and timezone-aware datetimes do not receive a combined range.
- Category frequency output can contain observed category values; callers must apply access
  controls before exposing profiles in future APIs or persistence.
- Bias-corrected skewness and excess kurtosis are undefined below three and four finite
  observations respectively; the exact formulas and constant-sample convention are documented.

## Next phase - not started

Phase 1E and all later functionality remain unimplemented.
