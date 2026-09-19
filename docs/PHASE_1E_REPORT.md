# HaraLens - Phase 1E Verification Report

## Summary

Phase 1E implements the reusable machinery for deterministic, independently executable,
typed, versioned, explainable, and serializable data-quality checks. It consumes a DataFrame,
its Phase 1C semantic profile, and its Phase 1D dataset profile. It adds no production check
catalogue, score, grade, recommendation, cleaning action, analytics, ML, UI workflow,
persistence, reporting, authentication, or AI behavior.

The implementation adds an explicit registry, immutable check and result contracts, a strict
configuration model, deterministic fingerprints, context consistency validation, formal
applicability, resource-policy seams, safe failure isolation, and neutral run aggregation.
Phase 1E registers no checks in the product. All reference checks are test fixtures.

No dependency, lockfile, ingestion, semantic-inference, profiling, API, or Streamlit source
was changed.

## Quality dimension taxonomy

Taxonomy version `1.0.0` defines:

- **completeness**: required information is present;
- **uniqueness**: records or values are distinct where a rule expects uniqueness;
- **validity**: values conform to expected type, domain, range, or rules;
- **consistency**: equivalent values and representations use compatible conventions;
- **integrity**: relationships, identifiers, and structural expectations remain coherent;
- **analytical_readiness**: a property can affect reliable analysis even when technically
  valid.

Dimension summaries contain counts only. They contain no score, weighting, percentage, grade,
or traffic-light status.

## Framework architecture

```text
DataFrame + DatasetSemanticProfile + DatasetProfile
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
        CheckExecutionResult[] + QualityRunResult
```

`haralens.quality` is independent of FastAPI, Streamlit, storage, visualization, scoring, and
AI packages.

## Check contract

`QualityCheck` is a Protocol with four responsibilities: validate its typed configuration,
select typed targets, assess applicability per target, and evaluate an applicable target.
`QualityCheckContext` exposes the table and trusted upstream artifacts through physical-column
helpers. Check implementations receive explicit resource limits and no arbitrary core
dictionaries.

The runner creates a pandas copy-on-write table snapshot for each check. Frozen semantic,
profile, definition, configuration, and result objects remain shared safely. Tests prove a
mutating test check cannot change caller-owned inputs or data observed by a later check.

## Check identity and versioning

Stable check IDs use the constrained `DQ_...` form. Display names are never identity. Every
definition, execution, and finding records `check_id` and semantic `check_version`.
Methodology changes therefore remain traceable. Framework version and dimension-taxonomy
version are separately fixed at `1.0.0`.

## Scope model

The typed scopes are `dataset`, `column`, and `multi_column`. Column targets carry both safe
name and physical position. Multi-column targets carry an ordered set of at least two unique
positions, which preserves relationship semantics for future composite rules. The runner
rejects duplicate, wrong-scope, mismatched, incomplete, and out-of-range targets. It orders
target executions by physical position.

## Execution status model

- `executed`: the rule ran successfully;
- `skipped`: configuration, missing prerequisites, or resource policy prevented execution;
- `not_applicable`: the rule does not logically apply to the target;
- `error`: an implementation problem prevented evaluation.

## Quality outcome model

Executed rules return `pass` or `fail`. Every unexecuted status returns `not_evaluated`.
Warning is deliberately absent because severity already expresses a finding's importance. A
pass cannot contain findings, and a failure must contain at least one. A software error can
never become a data-quality failure.

## Severity model

Findings use `critical`, `high`, `medium`, `low`, or `informational`. The check owns its
deterministic, versioned severity policy. Severity applies to one finding and does not produce
a dataset or dimension score.

## Affected-population model

Every affected population records affected count, population count, reconstructable
percentage, and one denominator basis: total rows, non-null rows, total cells, distinct
values, applicable values, or a described custom population. Zero populations yield `null`
because `0 / 0` is undefined. Models reject impossible counts and inconsistent percentages.

## Evidence model

Evidence contains a constrained metric name, typed source, finite scalar observation and
expectation, optional operator, profile-field reference, and bounded description. Conditions
represent common comparison operators without creating a rule DSL. There is no arbitrary
mapping or raw-example field. Finding messages, methodology fields, and warning codes are
also bounded and typed.

## Registry

`QualityCheckRegistry` uses explicit construction rather than import side effects. It
snapshots frozen definitions, rejects duplicate stable IDs, sorts by ID, supports lookup plus
dimension/scope filtering, exposes immutable tuples, and has a canonical SHA-256 fingerprint.

Registry tests cover empty, single, multiple, duplicate, deterministic order, lookup,
filters, snapshot safety, and fingerprint equivalence.

## Runner

`QualityCheckRunner` validates the context and configuration, resolves enablement, checks
prerequisites, validates check-owned configuration, selects and budgets targets, assesses
applicability, evaluates checks in stable order, materializes deterministic findings, and
builds neutral overall and per-dimension summaries.

Dataset checks execute once. Column checks preserve physical order. Multi-column dispatch is
supported without adding production relationship checks or an expression engine.

## Applicability

Applicability is an explicit per-target result with a safe reason code and message. A
semantically unsupported column becomes `not_applicable`; it does not inflate pass, fail, or
skip counts. A check that selects no targets also receives one neutral `not_applicable`
execution record.

## Error isolation

Typed prerequisite and resource limitations become `skipped`. Typed unsupported-data
limitations become `not_applicable`. Unexpected implementation exceptions are logged with a
constant message and bounded metadata, then become `error`/`not_evaluated` when fail-fast is
off. Fail-fast raises a redacted `UnexpectedCheckError`. Raw exception messages are absent
from logs and serialized results.

## Configuration and fingerprints

`QualityFrameworkConfig` is strict, frozen, and versioned. It supports enable/disable
overrides, dimension filters, fail-fast behavior, one typed parameter namespace per check,
and resource limits for registry size, targets, execution results, rows, regex values, and
column combinations. Unknown IDs, contradictory lists, duplicate namespaces/parameters,
unknown fields, malformed IDs, and non-positive budgets fail validation.

Canonical compact JSON and SHA-256 produce framework-configuration, per-check configuration,
and registry fingerprints. Configuration must not contain secrets.

## Determinism

The run reference derives from framework version, registry/configuration fingerprints, and
the complete semantic and dataset profiles. Finding identity additionally includes check ID
and version, target, per-check configuration, finding draft, and stable finding index. Logical
results contain no timestamps, durations, UUIDs, random values, or hash-order dependence.
Repeat-run tests compare entire result objects and finding IDs.

## Privacy/logging policy

Result APIs favor counts, finite percentages, thresholds, and profile references. They do not
provide an unrestricted raw-value evidence field. Operational logs may contain check identity,
dimension, physical column position, status, and safe error code. They do not contain raw
identifiers, values, categories, comments, or exception text. A regression test raises an
exception containing a distinctive private value and verifies it is absent from both logs and
results.

## Serialization

All result models are frozen, strict, reject non-finite numbers, forbid unknown fields, and
contain no DataFrame or arbitrary object. The representative full run round-trips through
standards-compliant JSON. Canonical serialization explicitly disallows `NaN`, `Infinity`, and
`-Infinity`. Nested model validators protect execution/finding identity and run-summary
integrity.

## Performance sanity observations

A bounded dispatch test registers 50 lightweight checks over 40 columns. Dimension filtering,
five explicit disables, and per-column applicability produce exactly 830 deterministic result
records: 400 executed passes, 400 not applicable, and 30 skipped. The test guards against
obvious registry/dispatch pathology; it is not a production throughput claim.

## Test-only/reference checks

Test fixtures exercise dataset, column, and multi-column scopes; pass/fail; informational and
high severity; applicability; disablement; prerequisites; expected limitations; unexpected
errors; configuration; resource limits; mutation attempts; and exact aggregation. These
classes live only in test files. The production registry remains empty, and HaraLens makes no
Phase 1F check claims.

## Validation results

The committed Phase 1D baseline had 390 green tests and green GitHub Actions. At the start of
this work, local Ruff, formatting, dependency compatibility, pre-commit, offline build, and
diff checks were green. Local pytest import was blocked by Windows Application Control before
Phase 1E changes were made.

For runtime validation, a process-local shim supplied only the three NumPy random type names
that pandas imports for annotations. HaraLens and its tests do not use `numpy.random`. The shim
changed no repository or environment files and allowed the installed pandas/numerical code to
run normally. Direct execution remains subject to the machine policy described under known
limitations.

| Check | Result |
| --- | --- |
| Full pytest with branch coverage | Passed: 424 passed, 0 failed, 0 skipped; 2 unchanged dependency warnings |
| Overall statement coverage | 97.11% (2,356/2,426) |
| Overall branch coverage | 91.31% (557/610) |
| Overall combined coverage | 95.95% |
| Focused Phase 1E tests | Passed: 34 |
| Quality-package statement coverage | 92.53% (669/723) |
| Quality-package branch coverage | 75.77% (147/194) |
| Quality-package combined coverage | 88.99% |
| Ruff lint/security | Passed: all checks |
| Ruff format | Passed: 83 files formatted |
| Strict mypy | Passed: 37 source files |
| Pre-commit | Passed: Ruff lint/security and format hooks |
| Dependency compatibility | Passed: all 77 installed packages compatible |
| Package build | Blocked: Hatchling absent from cache; DNS could not reach PyPI after 3 retries |
| FastAPI smoke | Passed with HTTP 200 and expected typed health body under the process-local shim |
| Streamlit smoke | Passed with HTTP 200, `ok` health, and served HTML; also started and responded without the shim |
| `git diff --check` | Passed; only informational LF-to-CRLF notices |
| Docker | Unavailable: Docker CLI is not installed |

The quality-focused branch percentage is driven mainly by defensive Pydantic invariant
rejection paths. Positive behavior, core failure isolation, context mismatch, privacy,
determinism, resource, and dispatch paths are exercised. The repository-wide coverage gate is
comfortably satisfied.

## File inventory

### Created

- `docs/QUALITY_FRAMEWORK.md`
- `docs/PHASE_1E_REPORT.md`
- `src/haralens/quality/__init__.py`
- `src/haralens/quality/config.py`
- `src/haralens/quality/contracts.py`
- `src/haralens/quality/errors.py`
- `src/haralens/quality/models.py`
- `src/haralens/quality/registry.py`
- `src/haralens/quality/runner.py`
- `tests/unit/test_quality_models_and_registry.py`
- `tests/unit/test_quality_runner.py`
- `tests/performance/test_quality_framework_sanity.py`

### Modified

- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

No file was deleted. `pyproject.toml` and `uv.lock` are unchanged. No dependency was added.

## Known limitations

- Current artifacts have no full content lineage fingerprint. Same-shape value substitution
  that preserves structural and profile facts can evade context matching. The future
  dataset-versioning/persistence layer should bind semantic, profile, and quality results to a
  canonical dataset-version content digest. Phase 1E avoids another expensive full-data hash.
- Check-specific row, regex, and combination budgets are cooperative. Future Phase 1F checks
  must enforce the budget relevant to their algorithm.
- pandas copy-on-write isolates tested cell, row, and column DataFrame API mutations between
  checks without eager full-table copies.
- No wall-clock duration appears in deterministic result bodies.
- Windows Application Control currently blocks
  `.venv/Lib/site-packages/numpy/random/_common...pyd`. Plain pytest and the FastAPI process
  therefore fail during pandas import on this machine. A non-persistent validation shim proves
  the suite and smoke behavior, but the host policy or Python environment still needs repair.
- The current network cannot resolve PyPI, and the user-level uv cache no longer contains
  Hatchling. A fresh package build could not be completed locally. An earlier unchanged
  baseline build succeeded, and no build configuration or dependency file changed.
- Docker validation cannot run without the Docker CLI.

## Errors encountered and resolved

- Windows policy rejected NumPy's `_common.pyd` before test collection. A dependency refresh
  was attempted twice, but the NumPy download stalled; a process-local annotation shim then
  enabled complete test and smoke validation without changing source or installed packages.
- The first focused Phase 1E run found three test expectation issues: two overly narrow error
  message matches and a definition snapshot whose default prerequisite tuple had not passed
  normalization. Error assertions were corrected, and default model validation now guarantees
  canonical prerequisite order. The rerun passed all 34 focused tests.
- Strict mypy found one local tuple-width inference error in multi-column target validation.
  An explicit variadic tuple annotation resolved it; strict mypy then passed all 37 source
  files.
- Workspace-local uv and pre-commit caches were used where the sandbox denied user cache
  writes. Temporary caches and validation shims were removed afterward.
- Offline and online package-build attempts could not resolve Hatchling. The online attempt
  confirmed a DNS failure after three retries; this remains an environment limitation.

## Principal commands and outcomes

| Command | Outcome |
| --- | --- |
| Repository status/log/file inspection and required document/source/test reads | Completed before modification; clean `main` at `05eac6d` |
| Direct baseline and final pytest invocations | Blocked during collection by Windows Application Control on NumPy `_common.pyd` |
| Process-local-shim focused pytest | Passed: 34 tests |
| Process-local-shim full pytest with branch coverage | Passed: 424 tests; coverage shown above |
| `python -m coverage report` / JSON summaries | Quality and complete statement/branch results recorded above |
| `python -m ruff check .` | Passed |
| `python -m ruff format --check .` | Passed: 83 files |
| `python -m mypy` | Passed: 37 source files |
| `python -m pre_commit run --all-files` with workspace cache | Passed |
| `uv pip check --python .venv/Scripts/python.exe` | Passed: 77 packages |
| `uv build --offline` | Blocked: Hatchling unavailable in cache |
| `uv build` | Blocked: PyPI DNS failure after three retries |
| `python scripts/smoke.py` under temporary process-local shim | FastAPI and Streamlit passed; owned processes stopped |
| Direct Streamlit start plus HTTP probes | Passed health and HTML checks; process stopped |
| `git diff --check` | Passed with line-ending notices only |
| `docker --version` | Docker CLI unavailable |

## Next recommended task

Phase 1F - production data-quality checks.

Phase 1F was not started.
