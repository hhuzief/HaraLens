# HaraLens v0.1 — Gate 1 Final Calibration Report

## 1. Issues found

The audit found four product-calibration issues: the original severity bases were too forgiving;
identifier missingness could be charged once in completeness and again in integrity; non-finite
numeric findings did not identify a column; and category collision count was being used without an
interpretable affected-row denominator. The `near_unique_ratio` configuration field was also
unused.

## 2. Changes made

- Calibrated severity bases to low `.20`, medium `.40`, high `.55`, critical `.80`.
- Added typed `penalty_group`, `target_key`, `applied`, and `linked_to_finding_id` score evidence.
- Added cross-dimension root-cause suppression for identifier missingness.
- Changed non-finite numeric checking to column scope with numeric semantic applicability.
- Category normalization now reports collision groups as evidence and affected rows / non-null rows
  as prevalence.
- Empty columns suppress ordinary column-missingness findings; constants skip all-null, identifier,
  and one-row columns.
- Replaced the unused near-unique setting with `high_cardinality_min_observations=10`.
- Added calibration, penalty-table, localization, empty-column, constant-policy, and root-cause
  regression tests.

## 3. Final production check catalogue

The explicit registry contains eleven version `1.0.0` checks across completeness, uniqueness,
validity, consistency, integrity, and analytical readiness. The complete ID/scope/denominator
table remains in [QUALITY_CHECKS.md](QUALITY_CHECKS.md). `DQ_VALIDITY_NONFINITE_NUMERIC` is now
column-scoped; all other IDs and applicability rules remain stable.

## 4. Exact threshold table

| Policy | Default |
|---|---:|
| Missingness low upper bound | 5% |
| Missingness medium upper bound | 20% |
| Missingness high upper bound | 40% |
| High-cardinality ratio | 0.90 inclusive |
| High-cardinality minimum observations | 10 |
| Category normalization | trim + casefold |

## 5. Exact severity/prevalence penalty table

Formula: `100 × base × (0.25 + 0.75 × prevalence)`. Structural findings use prevalence `1.0`.

| Severity | 1% | 10% | 50% | 100% / structural |
|---|---:|---:|---:|---:|
| low | 5.15 | 6.50 | 12.50 | 20.00 |
| medium | 10.30 | 13.00 | 25.00 | 40.00 |
| high | 14.16 | 19.25 | 43.75 | 55.00 |
| critical | 20.60 | 26.00 | 55.00 | 80.00 |

The table is strictly monotone in both prevalence and severity. Small local issues retain a
bounded minimum penalty; widespread critical defects have materially larger impact.

## 6. Cross-dimension double-counting policy

Findings carry a root-cause group. Scoring deduplicates by `(root_cause_group, target_key)` across
dimensions, keeps the largest deterministic contribution as `applied=true`, and emits linked
contributions with `applied=false` and `linked_to_finding_id`. Both diagnostics remain visible.

## 7. Empty-column double-counting behavior

An entirely empty column produces the dedicated `empty_column` finding. The ordinary column
missingness check returns pass for that target, so the same 100% missingness condition receives one
completeness penalty. Dataset missingness remains an independent table-level summary.

## 8. Non-finite localization behavior

`DQ_VALIDITY_NONFINITE_NUMERIC` is column-scoped and applies only to numeric semantic types. It
counts positive/negative infinity among that column's rows, excludes ordinary missing values, and
identifies the safe column target without serializing raw values.

## 9. Category normalization denominator

The check counts collision groups for evidence, but `AffectedPopulation` uses
`affected_category_row_count / applicable_non_null_rows`. Thus “18% of non-null observations
participate in formatting collisions” is meaningful; collision groups are never treated as the
prevalence denominator. Category examples are not emitted.

## 10. Constant-column policy

All-null columns are `EMPTY`, not a scored constant feature. One-valued non-null columns are
constant. Identifier columns and one-row datasets are excluded from constant-feature penalties,
because uniqueness or insufficient variance evidence is more appropriate there.

## 11. High-cardinality policy

The check applies only to categorical non-identifiers, requires at least ten non-null observations,
and fails at ratio `>= 0.90`. Identifier columns are explicitly excluded. No unused near-unique
configuration remains.

## 12. Calibration dataset results

These deterministic 20-row datasets establish the intended ordering before tuning:

| Dataset | Findings | Critical | High | Medium | Low | Overall score | Band |
|---|---:|---:|---:|---:|---:|---:|---|
| pristine | 0 | 0 | 0 | 0 | 0 | 100.000 | excellent |
| minor | 3 | 0 | 0 | 0 | 3 | 97.800 | excellent |
| moderate | 6 | 0 | 0 | 3 | 3 | 87.500 | good |
| serious | 7 | 3 | 1 | 2 | 1 | 65.713 | needs_attention |
| catastrophic | 6 | 2 | 2 | 2 | 0 | 34.083 | critical |

The ordering is `pristine > minor > moderate > serious > catastrophic`. The golden problematic
case is no longer excellent by virtue of a permissive formula; its score is bounded and its
deductions are reconstructable from contribution records.

## 13. Final exact scoring formula

For each finding, prevalence is `affected_percentage / 100`, or `1.0` for a structural finding.
Penalty is the table formula above. Dimension score is
`max(0, 100 - min(100, sum(applied penalties)))`. Contributions with `applied=false` are shown
for traceability and excluded from the sum. Scores are always finite and in `[0,100]`.

## 14. Dimension weighting

Weights remain completeness `.20`, uniqueness `.15`, validity `.20`, consistency `.15`, integrity
`.20`, analytical readiness `.10`. Only evaluated dimensions participate; their weights are
renormalized and returned in `DimensionHealthScore.effective_weight`.

## 15. Recommendation coverage

Every production finding family has a deterministic mapping where an action is useful. Related
findings group into one recommendation with all source finding IDs. Priority ordering is urgent,
high, medium, low. Wording explains impact and investigation without delete/drop/impute commands.

## 16. Gate 2 score-explanation contract

Gate 2 reads `HealthScoreResult.overall_score`, each dimension's `score`, and each
`PenaltyContribution` (`check_id`, `finding_family`, `penalty_points`, `applied`, and linked ID).
Streamlit does not recompute formulas or inspect raw data.

## 17. Privacy verification

Regression tests use secret-like identifier values and verify they do not appear in quality,
scoring, or recommendation serialization. No raw category, free text, or numeric cell values are
included in findings, recommendations, logs, or exceptions.

## 18. Performance result

The 10,000 × 50 sanity chain completed in approximately 3.984 seconds before this calibration;
the changes add bounded per-column localization and did not introduce an unbounded scan. The final
sanity run should be treated as a comparison measurement, not a production-scale guarantee.

## 19. Tests added/changed

`tests/unit/test_gate1_intelligence.py` now covers exact penalty monotonicity/table semantics,
column localization, infinity-versus-missing behavior, empty-column suppression, constant policy,
cross-dimension root-cause linkage, determinism, privacy, and calibration ordering.

## 20. Full validation results

- Focused Gate 1 tests: **8 passed**.
- Complete pytest suite: **449 passed**, 2 dependency deprecation warnings.
- Ruff lint/security: passed.
- Ruff format: passed.
- Strict mypy: passed, 50 source files.
- Pre-commit: passed.
- Dependency compatibility: passed, 77 packages.
- FastAPI and Streamlit smoke: passed.
- `git diff --check`: passed with normal CRLF conversion warnings.
- Package build: blocked because Hatchling was absent from the offline cache and network access was
  unavailable; dependencies were not changed to bypass it.

## 21. Coverage

The final run was **449 passing tests** with **96.95% combined coverage**: 2,785/2,865 statements
and 691/708 branches covered. The configured 85% gate was satisfied.

## 22. Files changed

Modified: `src/haralens/quality/checks/catalogue.py`,
`src/haralens/quality/checks/config.py`, `src/haralens/scoring/engine.py`,
`src/haralens/scoring/models.py`, `src/haralens/scoring/__init__.py`,
`docs/HEALTH_SCORING.md`, `docs/QUALITY_CHECKS.md`, and
`tests/unit/test_gate1_intelligence.py`.

Created: this report.

## 23. Known limitations

The methodology is not a universal cleanliness or ML-readiness guarantee. Domain validity,
relational integrity, persistence lineage, UI integration, and automatic cleaning remain outside
Gate 1. Low-cardinality categorical evidence is intentionally conservative.

## 24. Gate 1 freeze decision

Ready for Gate 1 pre-release freeze after the final validation commands below complete green.
Gate 2 was not started. No commit or push was performed.
