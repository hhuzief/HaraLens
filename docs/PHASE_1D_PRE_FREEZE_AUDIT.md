# HaraLens - Phase 1D pre-freeze profiling hardening audit

## Scope and baseline

This audit covers Phase 1D statistical correctness, category representation, deterministic
top-K selection, duplicate semantics and performance, resource boundaries, strict JSON,
operational privacy, and the table/semantic-profile consistency boundary. It does not add
quality checks, severity, scoring, recommendations, advanced EDA, ML, UI, persistence,
reporting, AI, or Phase 1E behavior.

The audit began from the current uncommitted Phase 1D working tree with 347 passing tests and
99.27% total coverage. All earlier Phase 1D files were preserved as the base for this audit.

## 1. Independent numerical correctness

### Finding

Mean, variance, standard deviation, skewness, and kurtosis already used values normalized by
the maximum absolute finite magnitude. Quartiles and median still used the original values.
Linear interpolation between opposite-sign values near `1e308` can overflow in the difference
between endpoints even when the correct quantile is finite. IQR then inherited that risk.

### Change

Median, Q1, Q3, and IQR now use the same normalized domain and are rescaled afterward. A
non-representable result remains `null`; the engine never substitutes a clipped value.

Independent tests compare HaraLens against Python's `statistics` module for mean, median,
sample/population variance, and sample/population standard deviation. Quantiles use a separate
Type-7 implementation. Skewness and kurtosis use explicit central-moment formulas rather than
calling HaraLens or pandas for expected values.

The deterministic matrix covers:

- `1, 2, 3, 4, 5`;
- mixed negative, zero, and positive values;
- repeated values;
- fractional values;
- one and two observations;
- values from `1e150` through `1.4e150`;
- opposite-sign and positive-only values approaching `1e308`;
- `NaN`, positive infinity, and negative infinity.

At the high end, `[-1e308, -5e307, 5e307, 1e308]` now returns mean/median `0`, Q1
`-6.25e307`, Q3 `6.25e307`, IQR `1.25e308`, and a finite sample standard deviation matching
the independently scaled standard-library result. Variance is correctly `null` because its
mathematical magnitude exceeds finite IEEE-754 range. `[8e307, 9e307, 1e308]` returns mean
`9e307`, Q1 `8.5e307`, Q3 `9.5e307`, and standard deviation `1e307` without naive-sum
overflow.

All independent floating comparisons use `math.isclose` with relative and absolute tolerance
`1e-12`. This admits ordinary binary rounding while remaining tight enough to detect an
estimator or interpolation-policy change.

## 2. Statistical definitions

The code model documentation and [profiling contract](PROFILING.md) now specify the complete
methodology.

- Variance is `sum((x-mean)^2)/(n-ddof)`. Default `ddof=1` is sample variance; configured
  `ddof=0` is population variance.
- Standard deviation is the non-negative square root of the same estimator.
- Q1, median, and Q3 use empirical index `h=(n-1)p` and the configured `linear`, `lower`,
  `higher`, `midpoint`, or `nearest` interpolation policy.
- Skewness is the bias-corrected Fisher-Pearson standardized third moment and requires at
  least three finite observations.
- Kurtosis is bias-corrected Fisher excess kurtosis, not Pearson kurtosis, and requires at
  least four finite observations.
- Constant samples meeting those moment sample sizes return `0.0` for skewness and kurtosis.
- `NaN` is null. Positive/negative infinity are non-null, separately counted, and excluded
  from finite aggregates. Non-numeric values are separately counted and excluded.
- Too-small, undefined, or non-representable finite results are `null`.

Regression tests lock every interpolation policy, both `ddof` values, moment formulas, minimum
sample requirements, and the constant-sample convention.

## 3. Category identity and display integrity

### Finding

The original frequency map keyed values by a rendered representation capped at 4,096
characters. Strings sharing that prefix could merge. Python dictionary equality can also
merge cross-type values such as `False` and `0` if type is not part of the key.

### Change

Frequency counting now uses a full typed identity before any display work:

- Boolean, integer, float, date, datetime, and string have separate tags;
- strings use complete content;
- floats use exact hexadecimal representation;
- dates and datetimes use full ISO representation.

The resulting categorical `category_count` and column cardinality use that same typed identity.
Tests prove that long strings differing after the first 200 characters remain two categories;
so do `1`/`"1"`, `True`/`"True"`, `False`/`0`, and a date/equivalent text.

Display truncation happens after counts and order are final. A truncated value includes the
visible prefix, original length, and full-string SHA-256 fingerprint. Thus equal visible
prefixes remain deterministically distinguishable with bounded output. The fingerprint is not
used for counting, so it cannot merge or change category counts.

## 4. Top-K determinism

Top-K ordering is descending count, then lexicographic canonical type tag, then complete
canonical identity representation. It never relies on dictionary or hash iteration order and
never directly compares unlike Python scalar objects.

Tests reorder equally frequent input categories and obtain the same top-K values. A tie across
the K boundary chooses the same categories and leaves the same exact remainder count.

## 5. Duplicate-row semantics

`duplicate_row_count` is the number of occurrences after the first equal row, equivalent to
`DataFrame.duplicated(keep="first").sum()`. Therefore `A, A, A` reports `2`, not `3`.

The audit covers no duplicates, one pair, three identical rows, missing-value duplicates,
mixed scalar columns, empty and single-row tables, zero-column tables, and unhashable object
content. An unsafe comparison yields `null` plus `DUPLICATE_COUNT_UNAVAILABLE`; it does not
become a quality finding.

## 6. Duplicate performance

The existing 100,000-row representative profile already performs exact duplicate detection.
An additional local measurement used five duplicate-only runs and three complete-profile runs
after semantic inference. Median results on this audit host were:

- exact duplicate calculation: `0.015016` seconds;
- complete Phase 1D profile: `0.405197` seconds;
- duplicate share: `3.71%`.

This is an environment-specific sanity measurement, not a performance guarantee. Exact
duplicate detection did not dominate representative bounded profiling, so no approximate
algorithm was introduced. At much larger future limits, exact duplicate work and temporary
hash structures remain an architecture consideration.

## 7. Resource boundaries

Rows, columns, and cells all use inclusive maxima. Tests with injected small limits cover
limit minus one, exact limit, and limit plus one for each dimension. Exactly the limit passes;
one over raises `RESOURCE_LIMIT_EXCEEDED` without partial output.

Cell count is `rows * columns` using Python arbitrary-precision integers, so it cannot wrap or
overflow. A regression uses a `10**100` configured cell maximum to lock that behavior without
allocating a large table.

## 8. JSON serialization

All profiling/config Pydantic models now set `allow_inf_nan=False`. Computation also converts
undefined or out-of-range results to `None`. A representative result containing source
infinities, undefined variance/moments, aware and ambiguous datetimes, mixed typed categories,
and long truncated categories is:

1. serialized with `model_dump_json()`;
2. parsed with a `parse_constant` callback that rejects non-standard constants;
3. emitted with standard-library `json.dumps(..., allow_nan=False)`;
4. round-tripped through `DatasetProfile.model_validate_json()`.

No bare `NaN`, `Infinity`, or `-Infinity` is emitted. A direct model construction test also
proves a non-finite computed field is rejected.

## 9. Operational privacy

Profiling contains no logging calls. A regression captures all logs while profiling data with
secret category/mode, identifier, free-text, datetime, and constant values and verifies none
appear. Raw exception text also remains excluded from typed warnings.

The profile contract still permits bounded categorical display labels. Identifier and free-
text profiles retain only lengths. This audit changes no access-control or persistence layer.

## 10. Semantic/profile consistency decision

The current checks verify shape, order, names, physical dtypes, total/null counts, and exact
distinct counts. They cannot detect every same-shape substitution or permutation that
preserves those facts.

No fingerprint was added in Phase 1D. A schema digest would not close the value-substitution
gap. A correct full-table fingerprint requires canonical rules for types, nulls, timezone
values, ordering, and source bytes and would add another exact pass. That belongs to the Phase
3 dataset-versioning/persistence layer, which should bind the existing `DatasetVersion`
content digest to semantic and profile results. Phase 4 service composition should enforce
the binding at workflow/API boundaries. Until then, the in-memory table and semantic profile
must be treated as one immutable analysis input. The risk is now explicit in the profiling
contract.

## Tests added or changed

Created `tests/unit/test_profiling_hardening.py` with 43 audit tests. Existing profiling tests
continue to pass with the new `category_count` and optional truncated-display fingerprint.
The representative 100,000-row performance test remains exact.

## Final validation

| Check | Result |
| --- | --- |
| Full pytest with branch coverage | Passed: 390 tests, 0 failed, 2 upstream warnings |
| Overall statement coverage | 99.06%: 1,687/1,703 statements |
| Overall branch coverage | 98.56%: 410/416 branches |
| Detailed profiling statement coverage | 96.77%: 449/464 statements |
| Detailed profiling branch coverage | 95.45%: 126/132 branches |
| Ruff lint/security | Passed |
| Ruff format check | Passed: 72 files formatted |
| Strict mypy | Passed: 30 source files |
| Pre-commit over tracked and untracked files | Passed |
| Dependency compatibility | Passed: all 77 installed packages compatible |
| Package build | Passed: sdist and wheel built offline |
| FastAPI smoke | Passed: HTTP 200 with expected HaraLens JSON |
| Streamlit smoke | Passed: health HTTP 200 and root served HTML |
| `git diff --check` | Passed; line-ending notices are informational |
| Docker | CLI unavailable locally |

The two warnings are unchanged upstream Starlette/AnyIO deprecations. The uncovered profiling
paths are defensive exception/fallback branches; the audit did not add tests solely to inflate
coverage.

## Files

### Created by this audit

- `docs/PHASE_1D_PRE_FREEZE_AUDIT.md`
- `tests/unit/test_profiling_hardening.py`

### Modified by this audit

- `README.md`
- `docs/PHASE_1D_REPORT.md`
- `docs/PROFILING.md`
- `src/haralens/profiling/config.py`
- `src/haralens/profiling/models.py`
- `src/haralens/profiling/service.py`

### Pre-existing Phase 1D working-tree files left unchanged by this audit

- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`
- `src/haralens/profiling/__init__.py`
- `src/haralens/profiling/errors.py`
- `tests/performance/test_profiling_sanity.py`
- `tests/unit/test_profiling.py`

No file was deleted. No dependency, lockfile, ingestion, semantic inference, API, UI, or later-
phase implementation changed. Together, the three lists above are the complete current Phase
1D working-tree inventory; the repository began this audit with the original Phase 1D files
still uncommitted.

## Audit execution notes

- The first new quantile/moment assertions used exact float equality and exposed ordinary
  normalization roundoff such as `15.000000000000002`. They were changed to the documented
  `1e-12` relative/absolute tolerance. No production calculation was weakened or rounded to
  make a test pass.
- The initial PowerShell attempt to parse coverage JSON could not handle case-sensitive path
  keys. Python's standard JSON parser read the same report and produced the exact statement
  and branch totals shown above.

## Remaining limitations

- Same-shape semantic/table substitutions can evade current consistency checks until version
  binding is implemented in Phases 3-4.
- Exact profiling and duplicate detection remain bounded in-memory operations.
- Deep pandas memory accounting remains an estimate for some Python objects.
- Variance can exceed finite output range even when standard deviation remains representable;
  it is then `null`, with no clipping.
- Category labels are bounded but can still contain observed business values under the
  documented profile contract. Future APIs/persistence must enforce authorization.

## Phase boundary

No Phase 1E or later-phase functionality was implemented.
