# HaraLens — Phase 1C verification report

## Phase 1C summary

Phase 1C implements a standalone, deterministic, versioned semantic type-inference engine.
It accepts a pandas `DataFrame` or Phase 1 ingestion result and returns an explainable typed
result for every physical column. It does not add profiling, quality scoring,
recommendations, API routes, Streamlit workflows, persistence, PII detection, ML, or AI.

The engine records physical dtype separately from inferred analytical meaning, computes
exact non-null and uniqueness metrics, bounds content inspection, preserves input and column
order, isolates pathological columns, and does not log or retain raw cell values.

## Semantic taxonomy

The version `1.0.0` primary types are:

- `numeric_continuous`
- `numeric_discrete`
- `categorical`
- `boolean`
- `datetime`
- `identifier`
- `free_text`
- `constant`
- `empty`
- `unknown`

Currency, percentage, and ordinal candidates were not added. Current evidence cannot assign
those meanings reliably without domain configuration, so adding them would imply precision
the engine does not have.

## Inference precedence

The final order is structural certainty, explicit physical evidence, strong lexical/content
evidence, then weaker cardinality evidence:

1. empty;
2. constant;
3. native or recognized textual boolean;
4. native datetime or Python date/datetime;
5. canonical UUID identifier;
6. sufficiently parseable date-like text;
7. numeric binary with a flag-name hint;
8. identifier supported by token-aware name, uniqueness, and optional structure;
9. numeric discrete/continuous;
10. native pandas category;
11. descriptive free text;
12. repeated bounded-cardinality text;
13. unknown.

This prevents null and constant behavior from being obscured, prevents uniqueness alone from
creating identifiers, gives real date syntax precedence over generic high cardinality, and
lets long repeated descriptions remain free text.

## Evidence system

`EvidenceCode` is a stable serialized enum. Every column result has at least one
`InferenceEvidence` containing a code, a safe readable message, and optional numeric observed
value/threshold. Evidence covers null/constant structure, physical dtypes, boolean sets,
identifier name and structure, UUIDs, date patterns and parse rates, numeric integrality,
cardinality, text length/structure, deterministic sampling, and safe inference failures.

`InferenceWarningCode` records ambiguity without putting raw values or exception details in
the result. `AlternativeSemanticCandidate` records an ordered alternate type, confidence,
and supporting evidence codes.

## Confidence method

Confidence is the discrete enum `high`, `medium`, or `low`:

- high: direct structural/physical evidence or multiple strong rules agree;
- medium: a documented heuristic wins but another interpretation is plausible;
- low: ambiguity, unsupported values, or insufficient evidence remains.

The engine reduces confidence below the configured non-null observation minimum. Empty and
constant results remain high because those properties are exact. Ambiguous slash dates are
always low because HaraLens does not assume a locale.

## Important heuristics

### Boolean

Detection trims and case-folds without mutating data. `true/false` is strong evidence;
`yes/no` and `y/n` are medium-confidence Boolean evidence. Numeric and textual `0/1` use the
same policy: a whole flag-name token is required for Boolean classification. Otherwise the
physical numeric/text category remains primary and Boolean is an explained alternative.
Arbitrary two-label categories remain categorical.

### Identifier

Canonical UUID text is strong evidence; repeated UUIDs receive reduced confidence and a
duplicate-value warning. Strong `id`/`uuid` name tokens require at least 0.80 uniqueness.
Contextual `account`/`code`/`key`/`number`/`no`/`reference` tokens also require an identifier
entity and are blocked by measurement/category context; generic reference additionally needs
value structure. CamelCase is split, so `CustomerID` matches while `identity_score` does not.
Monotonic integer and alphanumeric structure strengthen existing evidence but never force an
identifier alone. Uniqueness alone is never sufficient.

### Datetime

Native datetime dtypes, Python dates/datetimes, ISO calendar strings, and slash calendar
strings are supported. Parse success must meet the configured ratio and anchored syntax.
Compact integers, ordinal codes, partial year-month values, embedded product/version dates,
Unix timestamps, and arbitrary integers are not guessed. Slash dates valid in multiple
orders carry low confidence, a warning, and a categorical alternative. The engine does not
assign timezone meaning beyond a supplied offset.

### Numeric discrete/continuous

Fractional values and measurement-name hints support continuous numeric meaning. Integer-like
values use the absolute count threshold first. Above it, the ratio threshold requires
categorical name context; a low ratio alone no longer converts 500- or 2,000-valued
measurements to discrete. Complex numbers are unsupported and return unknown.

### Categorical and free text

Native pandas categories are categorical. Other strings must repeat. Absolute count is the
first boundary; above it, ratio evidence needs categorical name context. High-cardinality
generic labels remain unknown. Long descriptive text uses average length plus uniqueness,
whitespace/punctuation structure, or a descriptive-name hint. No NLP is used.

## Ambiguity handling

Results expose one primary type, zero or more alternatives, typed warnings, and confidence.
Tested conflicts include unique dates, numeric identifiers, amount-like unique numbers,
high-cardinality codes, numeric flags with and without name hints, ambiguous dates, and
unique short labels. Weak evidence returns `unknown` instead of forcing a category.

## Configuration

`SemanticInferenceConfig` is immutable, strict, and rejects unknown/coerced fields.

| Threshold | Default |
| --- | ---: |
| Categorical maximum distinct count | 20 |
| Categorical maximum distinct ratio | 0.05 |
| Identifier strong unique ratio | 0.98 |
| Identifier candidate unique ratio | 0.80 |
| Identifier minimum non-null count | 4 |
| Discrete numeric maximum distinct count | 20 |
| Discrete numeric maximum distinct ratio | 0.05 |
| Free-text minimum average length | 40.0 |
| Free-text minimum unique ratio | 0.50 |
| Free-text minimum whitespace/structure ratio | 0.50 |
| Datetime minimum parse ratio | 0.90 |
| Minimum confident non-null count | 10 |
| Maximum inspected content values | 10,000 |

Exact counts and uniqueness use all non-null values. Content rules use every value up to the
inspection limit, then evenly spaced deterministic positions including both ends. Sampling
status and count are present in each result.

## Dataset service and override extension

`SemanticInferenceService` processes columns by physical position, preserves order, returns
stable semantic-type counts and run metadata, and isolates an unexpected column failure as
unknown. It accepts `IngestionResult` without requiring ingestion changes.

`semantic_type` is the inferred type. The optional `user_confirmed_type` slot and
`effective_type` property provide a future override seam. Phase 1C implements no override
storage or UI.

## Tests added

The complete Phase 1C suite adds 148 deterministic cases across four files:

- all-null and constant numeric/string columns;
- native, textual, mixed-case, whitespace, and numeric boolean representations;
- unique/repeated UUID, numeric sequence, structured code, repeated code, name-token, and
  measurement identifier cases;
- native, Python object, ISO, timezone-suffixed, ambiguous, noisy, invalid, and
  integer-lookalike datetime cases;
- low/high-cardinality integer, fractional, integral-float, negative, zero-heavy, and complex
  numeric cases;
- native, low/medium/high-cardinality and Arrow-backed string cases;
- long, repeated, punctuated, categorical, and unique short text cases;
- null mixtures, exact threshold boundaries, deterministic sampling, confidence reduction,
  serialization, overrides, duplicate labels, failure isolation, and input immutability;
- customer and loan golden business tables with explicit expected types.
- pre-freeze business-name, Boolean symmetry, threshold-stage, datetime-lookalike,
  sampling-position, confidence, and bounded performance cases.

All 154 pre-Phase-1C tests remain unchanged and green.

## Validation results

| Check | Result |
| --- | --- |
| Full pytest with branch coverage | 302 passed, 0 failed, 0 skipped |
| Statement coverage | 99.93%: 1,239 statements, 1 missed |
| Branch coverage | 100%: 284/284 branches covered, 0 partial |
| Phase 1C package coverage | 100% statements and branches |
| Ruff lint/security | Passed |
| Ruff format check | Passed |
| Strict mypy | Passed: 25 source files |
| Pre-commit | Passed with workspace-local cache |
| Dependency compatibility | Passed: all 77 installed packages compatible |
| Package build | Source distribution and wheel built successfully |
| FastAPI smoke | HTTP 200 with expected HaraLens health JSON |
| Streamlit smoke | Health HTTP 200 and root served HTML |
| `git diff --check` | Passed; Windows line-ending notices are informational |
| Docker | Unavailable on PATH; not a Phase 1C failure |

The sole uncovered statement is `src/haralens/ingestion/csv.py:126`, the previously documented
defensive `StopIteration` translation after nonblank input and strict CSV filtering have
already established that a header exists. Forcing it requires mocking the standard-library
parser into an inconsistent state. Every Phase 1C statement and branch is covered.

Pytest reports two unchanged upstream Starlette/AnyIO deprecation warnings.

## File inventory

### Created

- `docs/SEMANTIC_INFERENCE.md`
- `docs/PHASE_1C_REPORT.md`
- `docs/PHASE_1C_PRE_FREEZE_AUDIT.md`
- `src/haralens/semantic/__init__.py`
- `src/haralens/semantic/config.py`
- `src/haralens/semantic/engine.py`
- `src/haralens/semantic/models.py`
- `src/haralens/semantic/service.py`
- `tests/unit/test_semantic_golden.py`
- `tests/unit/test_semantic_hardening.py`
- `tests/unit/test_semantic_inference.py`
- `tests/performance/test_semantic_inference_sanity.py`

### Modified

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

No files were deleted. Ingestion files, application entry points, dependencies,
`pyproject.toml`, and `uv.lock` were not changed.

## Known limitations

- Semantic inference remains heuristic and cannot establish business ground truth.
- Ambiguous dates are detected but not resolved; locale configuration is absent.
- Exact uniqueness still scans each full bounded column and may be material at combined
  Phase 1B row/column maxima.
- Deterministic samples can miss rare value patterns; sampled results say so explicitly.
- PII, email, currency, percentage, ordinal, Unix-time, and schema-aware inference are out of
  scope.
- Unsupported or unhashable object values return unknown; the service does not analyze nested
  structures.
- User override persistence and presentation are future work.

## Errors encountered and resolved

- Initial concurrent baseline `uv` commands raced while initializing the default Windows
  user cache. Rerunning with repository `.uv-cache` completed normally.
- Baseline pre-commit could not write its default user cache in the restricted environment.
  Setting `PRE_COMMIT_HOME` to the repository cache resolved it without changing hooks.
- The first focused run exposed an overly restrictive UUID test pattern and a computed-field
  JSON round-trip mismatch. UUID validation now accepts canonical textual groups and confirms
  them with `uuid.UUID`; `effective_type` is a derived property while the serialized override
  slot remains explicit.
- Coverage review exposed that complex numeric dtypes had no defensible continuous/discrete
  meaning. They now return a typed, explained unknown result.

No implementation error remains unresolved.

## Next recommended task — not started

**Phase 1D — dataset and column profiling.**
