# HaraLens v0.1 production quality checks

Gate 1 registers eleven deterministic checks through `create_default_quality_registry()`.
The registry is explicit, sorted by stable ID, and has no import-time registration.

| ID | Version | Dimension | Scope | Denominator / applicability |
|---|---|---|---|---|
| DQ_COMPLETENESS_DATASET_MISSINGNESS | 1.0.0 | completeness | dataset | total cells |
| DQ_COMPLETENESS_COLUMN_MISSINGNESS | 1.0.0 | completeness | column | total rows |
| DQ_COMPLETENESS_EMPTY_COLUMN | 1.0.0 | completeness | column | total rows; all-null columns |
| DQ_UNIQUENESS_DUPLICATE_ROWS | 1.0.0 | uniqueness | dataset | total rows; duplicate occurrences beyond first |
| DQ_UNIQUENESS_IDENTIFIER_VALUES | 1.0.0 | uniqueness | column | non-null identifier rows |
| DQ_VALIDITY_NONFINITE_NUMERIC | 1.0.0 | validity | column | numeric column rows; infinity values only |
| DQ_CONSISTENCY_COLUMN_NAME_WHITESPACE | 1.0.0 | consistency | dataset | column labels |
| DQ_CONSISTENCY_CATEGORY_NORMALIZATION | 1.0.0 | consistency | column | categorical columns; collision count |
| DQ_INTEGRITY_IDENTIFIER_MISSINGNESS | 1.0.0 | integrity | column | identifier total rows |
| DQ_READINESS_CONSTANT_COLUMN | 1.0.0 | analytical_readiness | column | observed values |
| DQ_READINESS_HIGH_CARDINALITY | 1.0.0 | analytical_readiness | column | categorical non-identifiers |

Missingness thresholds are 0% pass, >0–5% low, >5–20% medium, >20–40% high, and >40%
critical. A zero denominator produces a null affected percentage through the Phase 1E
population contract. Findings contain counts and bounded metadata only; raw values are never
included.

Category normalization reports collision-group count as evidence, but prevalence is affected rows
in collision groups divided by applicable non-null rows. Empty columns use the dedicated
empty-column check; ordinary column missingness skips an entirely empty column to avoid a second
full penalty. Constant-column readiness skips all-null columns, identifier columns, and one-row
tables.

High-cardinality applies only to categorical non-identifiers with at least ten non-null
observations and an observed cardinality ratio of at least 0.90. There is no unused near-unique
threshold in the production configuration.
