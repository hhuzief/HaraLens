# Quality-check framework

## Boundary

Phase 1E provides the quality-check framework. The production quality-check catalogue is
implemented in Phase 1F.

Profiling states descriptive facts such as `missing_percentage = 14.3`. A quality check
applies an explicit expectation to such facts and records whether the expectation passed.
The profiling package remains judgment-free; thresholds and severity policy belong to each
future production check. This framework does not score, grade, recommend, clean, persist, or
display results.

```text
DataFrame + Semantic Profile + Dataset Profile
                       |
                       v
             QualityCheckContext
                       |
                       v
             QualityCheckRegistry
                       |
                       v
              QualityCheckRunner
                       |
                       v
       CheckExecutionResult[] -> QualityRunResult
```

The package imports neither FastAPI nor Streamlit. It uses no database, visualization, AI,
or persistence service.

## Versioned quality dimensions

Taxonomy version `1.0.0` defines six non-overlapping dimensions:

| Dimension | Meaning |
| --- | --- |
| `completeness` | Information required by a rule is present. |
| `uniqueness` | Records or values are distinct where a rule expects uniqueness. |
| `validity` | Values conform to an expected type, domain, range, or rule. |
| `consistency` | Equivalent values or representations follow compatible conventions. |
| `integrity` | Identifiers, relationships, and structural expectations remain coherent. |
| `analytical_readiness` | A property may affect reliable statistical or ML analysis even when technically valid. |

These are labels for checks and neutral result aggregation. They do not produce dimension
scores. A taxonomy meaning change requires a new taxonomy version.

## Check contract and identity

`QualityCheck` is a small Protocol. A check provides a frozen `QualityCheckDefinition` and
implements configuration validation, target selection, applicability assessment, and
evaluation. It receives a `QualityCheckContext`, a typed target and configuration, plus
explicit resource limits. No untyped core dictionary is passed between the runner and a
check.

Stable IDs use `DQ_...` uppercase identifiers and never derive from display names. Every
definition records a semantic `check_version`; methodology changes require that version to
change. Definitions also carry a dimension, scope, safe description, supported semantic
types, tags, prerequisites, and default-enabled state. Every execution and finding repeats
the ID and version so historical output remains interpretable.

The framework version is `1.0.0`. It identifies runner/result semantics and is independent
from check methodology and dimension-taxonomy versions.

## Scopes and targets

- `dataset` checks select exactly one dataset target when applicable.
- `column` targets identify both the physical source position and its safe column name.
- `multi_column` targets contain at least two unique physical positions and matching names.

The runner validates targets against the trusted profile and sorts them by physical position.
This preserves source-column order even if a check returns targets in another order. Duplicate,
out-of-range, wrong-scope, or name/position-mismatched targets are implementation errors. The
multi-column shape supports later composite and cross-column checks without introducing an
expression language or relational-database scope.

## Execution status, outcome, and severity

Execution state and data-quality outcome are separate:

| Execution status | Meaning |
| --- | --- |
| `executed` | The implementation evaluated the rule successfully. |
| `skipped` | The rule could apply but configuration, a missing prerequisite, or resource policy prevented execution. |
| `not_applicable` | The rule does not logically apply to the selected target. |
| `error` | An unexpected check implementation problem prevented evaluation. |

An executed check returns `pass` or `fail`. Every other status returns `not_evaluated`.
There is no warning outcome. Failed findings may use `critical`, `high`, `medium`, or `low`.
`informational` is reserved for a future non-failure observation mechanism and model
validation rejects it on `FindingDraft` and `QualityFinding`. Each check owns and versions its
deterministic severity policy. Severity describes one finding and never becomes an overall or
dimension health score.

A pass has no findings. A failure has at least one structured finding. A software error is
never represented as a quality failure.

## Findings, affected populations, conditions, and evidence

`QualityFinding` records a deterministic ID, run reference, check identity and version,
dimension, scope, physical target, failed outcome, severity, safe message, affected
population, optional expected condition, structured evidence, methodology metadata, and
typed warning codes.

An affected population always carries `affected_count`, `population_count`, calculated
percentage, and a denominator basis:

- `total_rows`
- `non_null_rows`
- `total_cells`
- `distinct_values`
- `applicable_values`
- `custom`, which requires a bounded explanation

When population count is zero, affected count must also be zero and affected percentage is
`null`, because `0 / 0` is undefined. For a positive population, percentage is exactly
`affected_count / population_count * 100`. The model rejects an affected count larger than its
population, fabricated zero-population percentages, missing positive-population percentages,
and percentages that cannot be reconstructed from the counts. Neutral summaries never
coerce the nullable percentage to zero.

Conditions represent a bounded metric, operator, expected scalar, and optional description.
Evidence identifies a safe metric and source (`table`, semantic/profile artifact, column
profile, or configuration), with optional finite scalar values, operator, and profile-field
reference. Evidence has no arbitrary mapping or raw-value field. Check authors must express
aggregate facts and must not place identifiers, invalid cell examples, categories, comments,
or other source content in evidence, messages, methodology, or warning codes.

## Context consistency and immutability

Before dispatch, the runner checks table/profile row and column counts, cell and missing-cell
counts, column order, physical name and position, dtype, null and non-null counts, semantic
type/confidence, inference version, and available distinct counts. It rejects detectable stale
or mixed artifacts with a typed `QualityContextError`.

Current upstream artifacts have no complete content fingerprint. A same-shape substitution or
permutation that preserves dtype, null counts, cardinality, and all material profile outputs
can evade consistency checks. Full logical lineage belongs to the future dataset-versioning
and persistence layer; Phase 1E deliberately avoids a second full-data cryptographic scan.
Before persisted quality runs, API-driven cross-session analysis, scheduled analysis, or
dataset versioning are introduced, all ingestion, semantic, profiling, and quality artifacts
must bind to one canonical dataset-version/content digest.

Pydantic artifacts, configuration, definitions, and result models are frozen. Each check
receives its own shallow DataFrame snapshot under pandas 3's always-on copy-on-write behavior.
Cell assignment, row assignment, and column insertion detach only the mutating check's blocks;
later checks and the caller continue to observe the original table. Regression tests perform
all three mutations and verify isolation. This adds DataFrame metadata work per check and
copies data blocks only when a check writes, avoiding an eager full-table copy for normal
read-only checks. The framework performs no cleaning or repair.

## Explicit registry

`QualityCheckRegistry` receives check instances explicitly. It performs no import-time
discovery or registration. Construction snapshots each frozen definition, rejects duplicate
IDs, and sorts entries by stable check ID. Listing, lookup, dimension filtering, scope
filtering, and a canonical SHA-256 registry fingerprint are deterministic. The registry holds
the implementations needed for execution but exposes its entry collection as an immutable
tuple.

Phase 1E registers no production checks. Reference checks exist only inside tests.

## Runner and applicability

The runner performs these steps:

1. validate context, registry limits, and referenced configuration IDs;
2. create a private copy-on-write table snapshot for each enabled check;
3. process definitions by check ID;
4. resolve default, explicit, and dimension-filter enablement;
5. validate the check-owned configuration namespace;
6. verify declared upstream prerequisites;
7. select, validate, budget, and order targets;
8. assess applicability per target;
9. evaluate applicable targets and materialize deterministic findings;
10. build neutral overall and per-dimension counts.

Checks may depend on the table, semantic profile, dataset profile, and optional ingestion
metadata. They do not depend on one another, so there is no check dependency graph or hidden
execution ordering.

## Error isolation and fail-fast behavior

Expected limitations are typed:

- `CheckPrerequisiteError` and `CheckResourceLimitError` produce `skipped` results;
- `CheckDataUnsupportedError` produces `not_applicable`;
- unexpected exceptions produce `error` and `not_evaluated` when fail-fast is disabled;
- fail-fast converts the unexpected failure to a safely redacted `UnexpectedCheckError`.

Raw exception strings never enter output or logs. Operational logging records a constant
message and bounded metadata such as check ID, version, dimension, physical column position,
and error code. Check code must never log raw table values.

## Configuration, resources, and fingerprints

`QualityFrameworkConfig` is strict, frozen, and versioned. It supports explicit enable and
disable overrides, an optional dimension filter, internal-error fail-fast behavior, one typed
namespace per check, and resource limits. Check-specific parameter names are constrained and
unique; checks validate their own parameters. Configuration must not contain secrets.

The Phase 1E resource seam bounds registered checks, targets per check, total execution
records, rows available to a check, regex-inspected values, and column combinations. The
runner enforces registry, target, and total execution limits. Future checks must enforce the
row/regex/combination limits relevant to their algorithms. This is a budgeting contract, not
a scheduler or timeout system.

Configuration and registry fingerprints use SHA-256 over sorted, compact, standards-compliant
JSON. Each execution also carries a per-check configuration fingerprint. The run reference
derives from the framework version, registry/configuration fingerprints, and complete semantic
and dataset profiles. Finding IDs additionally include check version, target, configuration,
finding draft, and stable index.

No timestamp, random UUID, duration, or hash-order dependence appears in logical result
content. Identical trusted artifacts, registry, configuration, and versions produce identical
results.

## Serialization and privacy

All result models forbid non-finite floats and arbitrary objects. They round-trip through
strict Pydantic JSON, and canonical fingerprint serialization uses `allow_nan=False`.
DataFrames remain in context and never enter result bodies.

The evidence contract favors finite counts, percentages, thresholds, and references. It does
not offer a generic raw-example field. Column names and positions may appear because they are
target identity. Future API/persistence access control remains outside Phase 1E.

## Extending the framework in Phase 1F

For each production check:

1. choose one existing dimension and scope;
2. define a stable `DQ_...` ID and methodology version;
3. declare semantic support and upstream prerequisites;
4. define a small typed configuration model and deterministic severity policy;
5. select physical targets deterministically;
6. return formal applicability before evaluating;
7. honor the relevant resource limits;
8. emit aggregate, privacy-safe evidence and reconstructable affected populations;
9. test thresholds, limits, failure isolation, serialization, privacy, and determinism;
10. add it to an explicit composition-root registry.

Do not modify profiling to accommodate thresholds. Do not introduce scoring,
recommendations, or mutation into a check.

## Known limitations

- Complete content lineage is a prerequisite for persisted or cross-session execution as
  described above.
- Resource limits are cooperative for check-specific scans; Python cannot forcibly interrupt
  an arbitrary implementation inside this synchronous runner.
- pandas copy-on-write protects DataFrame API mutations between checks. Mutation through
  unsupported pandas internals or in-place mutation of a mutable Python object stored inside
  an object cell is outside this guarantee and must not be used by production checks.
- The framework does not capture wall-clock duration in deterministic result bodies.
- There are no production checks, persistence adapters, API routes, UI workflows, scores,
  recommendations, or repair actions in Phase 1E.
