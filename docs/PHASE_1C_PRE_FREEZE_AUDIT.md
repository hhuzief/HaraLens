# HaraLens — Phase 1C pre-freeze semantic hardening audit

## Scope

This audit stress-tests Phase 1C semantic correctness, ambiguity, deterministic sampling,
confidence, and bounded-size performance. It does not implement profiling, quality checks,
PII detection, application endpoints, UI workflows, persistence, ML, AI, or Phase 1D.
Ingestion behavior and dependencies are unchanged.

The audit began from 242 passing tests with complete semantic-package branch coverage.

## 1. Identifier false-positive audit

### Finding

The prior rule treated `code`, `number`, `no`, `key`, and `account` like equally strong
identifier hints. With high uniqueness, names such as `number_of_children` could therefore
become identifiers. Value structure strengthened confidence but the name hierarchy did not
distinguish direct and contextual evidence.

### Final evidence hierarchy

1. Canonical UUID text is direct identifier structure. A strong uniqueness ratio yields high
   confidence when fully inspected. Repeated UUIDs retain identifier meaning with medium
   confidence and a duplicate warning.
2. Strong tokens `id` and `uuid` require at least the configured 0.80 candidate uniqueness.
   Strong uniqueness of 0.98 plus monotonic/code structure can reach high confidence.
3. Contextual tokens `account`, `code`, `key`, `number`, `no`, and `reference` require an
   identifier entity token such as customer, account, invoice, order, product, phone,
   transaction, record, or user. Measurement/category context blocks contextual hints.
   Generic `reference` additionally requires value structure.
4. Monotonic integers and structured alphanumeric codes only strengthen qualifying name and
   uniqueness evidence. They never independently force identifiers.

Names alone and uniqueness alone never decide identifier type. Candidate uniqueness from
0.80 up to 0.98 retains plausible repeated identifiers at medium confidence when structured
and low confidence when unstructured. Ratios below 0.80 do not infer an identifier.

The regression matrix covers every requested name. Expected outcomes include identifiers for
customer/account/invoice/order/product/phone/transaction/reference identifiers; numeric
measurements for identity score, number of children, balance, and account age; and unknown for
unique postal codes without enough row-identifier evidence.

## 2. Boolean asymmetry audit

### Finding and revision

Treating textual `"0"/"1"` as intrinsically Boolean while requiring name support for numeric
`0/1` was not semantically defensible. Storage representation does not establish whether a
binary value is a flag, target class, rating, or two-category code.

The final symmetric policy is:

- native Boolean dtype: Boolean, high confidence;
- fully inspected `true/false`: Boolean, high confidence;
- `yes/no` and `y/n`: Boolean, medium confidence;
- numeric or textual `0/1` plus a flag token (`is`, `has`, `flag`, `active`, `enabled`, and
  related configured tokens): Boolean with a physical-type alternative;
- numeric `0/1` without a flag token: `numeric_discrete` with Boolean alternative and warning;
- textual `0/1` without a flag token: `categorical` with Boolean alternative and warning.

The exact full-column distinct count must be two before any sampled `0/1` rule can fire.
`is_active` and `has_defaulted` are Boolean; loan status, segment, rating, binary target, and
unknown-name cases retain the more conservative physical-family result when name support is
absent.

## 3. Categorical and discrete threshold audit

### Finding and revision

The former unconditional count-OR-ratio rule classified 500/20,000 and 2,000/100,000 generic
values as categorical/discrete solely because their ratios were below 0.05. That could turn
high-cardinality measurements into discrete features and created an undocumented ratio cliff.

The final staged policy preserves both configurable thresholds:

1. Measurement-name evidence selects continuous numeric behavior first.
2. For integer-like numeric values, distinct count at or below 20 selects discrete.
3. Above 20, the 0.05 ratio selects discrete only with categorical name context.
4. Otherwise high-cardinality numeric values are continuous.
5. Text must repeat. Distinct count at or below 20 selects categorical.
6. Above 20, the 0.05 ratio selects categorical only with categorical name context.
7. Otherwise generic high-cardinality text remains unknown unless free-text evidence applies.

Therefore the relationship is staged, rather than unconditional AND or OR. The 20/21
absolute boundary remains explicit and configurable: 20/100 is bounded-cardinality while
21/100 needs other evidence. Generic 500/20,000 and 2,000/100,000 values no longer cross type
families from ratio alone. Named integer category codes can still use ratio evidence.

## 4. Datetime false-positive audit

The anchored syntax gate already prevented most date-like identifiers. Regression cases now
lock the policy:

- compact integers `20240101` remain numeric;
- ordinal-looking `2024-001` values remain non-datetime;
- partial year-month `2024-01` values remain non-datetime in Phase 1C;
- product/version strings containing date segments remain non-datetime;
- parseable-looking prose does not qualify because syntax is not anchored;
- ambiguous slash dates remain datetime with low confidence, a warning, and no locale choice;
- explicit timezone offsets are accepted as supplied syntax, without inferred timezone
  meaning.

Parse rate is necessary but cannot bypass the syntax gate or identifier-name conflict rule.

## 5. Sampling stability audit

Content inspection remains deterministic and random-free. Above the configured maximum, the
engine uses evenly spaced non-null physical positions. Tests prove:

- repeated runs produce equal typed results;
- changing DataFrame index labels alone does not change results;
- the first and last physical non-null positions participate;
- `sampled`, `sample_count`, and `DETERMINISTIC_SAMPLE` are correct;
- full-column null, non-null, distinct count, and distinct ratio remain exact.

Content-derived high confidence is reduced to medium when sampling is active. Native dtype
evidence remains high because it describes the full physical column. Rare patterns between
sampled positions can still be missed and remain a documented limitation.

## 6. Performance sanity

Three warm-process runs per scenario were measured locally on the audit environment
(Windows, Python 3.12, pandas 3). The table reports the median inference wall time, pandas
deep-memory estimate for the input frame, and maximum Python allocation traced during
inference. `tracemalloc` does not include every native-library allocation, so these are local
diagnostic observations rather than guarantees or marketing benchmarks.

| Scenario | Median inference | DataFrame deep memory | Max traced inference allocation |
| --- | ---: | ---: | ---: |
| 100,000-row numeric column | 0.0863 s | 0.76 MiB | 3.89 MiB |
| 100,000 unique strings | 0.1951 s | 1.91 MiB | 1.76 MiB |
| 100,000 rows × 4 representative columns | 0.3770 s | 3.83 MiB | 3.88 MiB |

The observed results were respectively numeric continuous, unknown high-cardinality text,
and identifier/numeric continuous/categorical/Boolean. No obviously pathological behavior
was observed. Exact uniqueness remains intentionally unchanged and still scans each complete
bounded column.

## 7. Confidence audit

Every high-confidence path was reviewed. High is now limited to:

- exact empty or constant structure;
- native Boolean, datetime, or pandas category dtype;
- fully inspected canonical UUID with strong uniqueness;
- fully inspected `true/false` and unambiguous supported date syntax;
- exact binary values plus flag-name evidence;
- physical fractional numerics;
- fully inspected, strongly unique identifiers with name and structure evidence.

Inferred text categories and free text are capped at medium. Sampled content rules cannot
return high. `yes/no`, repeated identifiers, partially parsed dates, ambiguous dates, and
other heuristic conflicts are medium or low. Tests assert both the allowed strong cases and
representative heuristic cases that must not be high.

## Changes made

- Added strong/contextual identifier token tiers, entity context, blocker context, and a
  validated 0.80 candidate uniqueness threshold.
- Added typed evidence for candidate uniqueness, textual binary sets, and categorical name
  context.
- Made textual and numeric `0/1` inference symmetric.
- Changed count/ratio interaction to staged evidence with name-gated ratio rules.
- Required exact distinct-count support for sampled binary inference.
- Reduced sampled content, inferred category, free-text, and repeated-ID confidence.
- Added identifier, Boolean, threshold, datetime, sampling, confidence, and bounded-size
  performance regressions.
- Updated semantic policy and Phase 1C documentation.

## Tests and coverage

- 302 passed, 0 failed, 0 skipped.
- 99.93% statement coverage: 1,239 statements, one missed.
- 100% branch coverage: 284/284, zero partial branches.
- Semantic package: 100% statements and branches.
- The audit adds a net 60 cases over the 242-test starting state.

The only missed project statement remains `src/haralens/ingestion/csv.py:126`, the documented
defensive parser-state translation that cannot be reached through consistent normal input.

## Final validation

| Check | Result |
| --- | --- |
| Full pytest with detailed branch coverage | Passed: 302 tests |
| Ruff lint/security | Passed |
| Ruff format check | Passed |
| Strict mypy | Passed: 25 source files |
| Pre-commit over tracked and new files | Passed |
| Dependency compatibility | Passed: 77 packages compatible |
| Package build | Source distribution and wheel built successfully |
| FastAPI smoke | HTTP 200 with expected health JSON |
| Streamlit smoke | Health HTTP 200 and root HTML served |
| `git diff --check` | Passed; line-ending notices are informational |
| Docker | Unavailable on PATH; not a Phase 1C failure |

Pytest retains two upstream Starlette/AnyIO deprecation warnings.

## Audit file inventory

### Created

- `docs/PHASE_1C_PRE_FREEZE_AUDIT.md`
- `tests/performance/test_semantic_inference_sanity.py`
- `tests/unit/test_semantic_hardening.py`

### Modified

- `docs/PHASE_1C_REPORT.md`
- `docs/SEMANTIC_INFERENCE.md`
- `src/haralens/semantic/config.py`
- `src/haralens/semantic/engine.py`
- `src/haralens/semantic/models.py`
- `tests/unit/test_semantic_inference.py`

No files were deleted. Ingestion, application entry points, dependencies, `pyproject.toml`,
and `uv.lock` were unchanged.

## Known limitations

- Semantic inference remains heuristic and cannot determine business ground truth.
- The entity/context token vocabulary is intentionally finite; unfamiliar domain naming may
  remain unknown or need user confirmation.
- The explicit 20/21 absolute count boundary remains a configurable classification boundary.
- Ambiguous dates are detected but not locale-resolved; partial year-months are unsupported.
- Exact uniqueness scans the full bounded column.
- Deterministic sampling can miss rare patterns between selected positions.
- PII, currency, percentage, ordinal, Unix-time, schema-aware inference, and override
  persistence remain out of scope.

## Errors encountered

The audit found three semantic overreach issues: contextual identifier tokens were too
strong, textual `0/1` received stronger treatment than numeric `0/1`, and ratio-only
cardinality could override analytical context. All three were corrected with typed evidence
and regressions. A focused format check caught one long test line before final validation.
No implementation error remains unresolved.

## Next task — not started

**Phase 1D — dataset and column profiling.**
