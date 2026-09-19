# HaraLens - Phase 1E Pre-Freeze Audit

## Zero-population policy

`AffectedPopulation` now treats a zero denominator as mathematically undefined:

- `population_count == 0` requires `affected_count == 0`;
- `affected_percentage` is `None` and serializes as JSON `null`;
- a fabricated `0.0%` for a zero population is rejected;
- a positive population requires a finite percentage equal to
  `affected_count / population_count * 100`;
- affected count greater than population count remains invalid.

Regression cases lock `0/0 -> null`, `0/1 -> 0.0`, `1/1 -> 100.0`, and
`25/100 -> 25.0`. Run summaries aggregate execution/finding counts only and never coerce the
nullable percentage to zero.

## Severity/outcome policy

Every current finding represents a failed quality condition. `FAIL + INFORMATIONAL` was
therefore contradictory. Failed `FindingDraft` and `QualityFinding` objects now accept only
`LOW`, `MEDIUM`, `HIGH`, or `CRITICAL`.

`INFORMATIONAL` remains in the stable severity taxonomy but is reserved for a future typed
non-failure observation mechanism. Phase 1E does not add such an outcome or observation model.
Both draft construction and deserialization of a final finding reject informational failure
severity.

## Check isolation architecture

The previous runner made one eager deep DataFrame copy for the whole run. That protected the
caller but let Check A alter data observed by Check B.

The runner now creates one `DataFrame.copy(deep=False)` snapshot for each enabled check. The
project requires pandas 3.x, where copy-on-write is always active. DataFrame API writes detach
the affected blocks for that check, while read-only checks share the original blocks. This
provides check-to-check isolation without copying every cell for every normal check.

A malicious test-only check performs all of the following:

- cell assignment through `iloc`;
- column insertion;
- row insertion through `loc`.

A later check observes the exact original DataFrame, and the caller-owned DataFrame also
remains unchanged. Registry construction order is reversed in the test, while stable check-ID
ordering still produces the same isolated sequence.

Copy-on-write protects supported DataFrame API mutations. Direct mutation through pandas
private internals or in-place mutation of a mutable Python object stored inside an object cell
is outside the guarantee and is prohibited for production checks.

## Coverage review

Tests were added for behavior with material framework value: zero denominators, severity and
outcome coherence, duplicate model metadata, target validation, condition/evidence rules,
configuration contradictions, copy-on-write isolation, result/finding integrity, typed error
propagation, execution budgets, no-target applicability, context version/cardinality mismatch,
fingerprint equivalence, and identity changes.

After the audit, full-suite quality-package coverage is:

- statements: **99.20%** (`741/747`);
- branches: **98.54%** (`203/206`);
- combined: **99.04%**.

The audit deliberately did not fabricate invalid Pydantic instances or unsafe table internals
solely to reach 100%.

## Fingerprint stability

Canonical fingerprints are invariant under:

- enabled-check ID order;
- disabled-check ID order;
- included-dimension order;
- per-check parameter order;
- per-check configuration order;
- registry construction order.

Canonical models sort these collections before compact, sorted-key JSON is hashed. Tests also
prove that a meaningful fail-fast or threshold change produces a different configuration or
run fingerprint.

## Identity determinism

Repeated execution with the same artifacts, registry, configuration, framework/check
versions, targets, and findings produces the same run reference and finding IDs.

The audit locks these identity effects:

- check-version change: run reference and finding ID change;
- threshold/configuration change: run reference and finding ID change;
- framework-version change: run reference changes;
- target-column change: run reference stays stable, finding ID changes;
- severity change: run reference stays stable, finding ID changes;
- evidence change: run reference stays stable, finding ID changes.

No timestamp, duration, random UUID, or uncontrolled hash ordering enters logical identity.

## Dataset-lineage decision

Current in-memory consistency validation remains appropriate for Phase 1E. It detects shape,
order, name, dtype, row/null/distinct-count, semantic, profile, and version mismatches without
performing another expensive full-data hash.

It cannot prove lineage when a same-shape substitution preserves those facts. Before HaraLens
introduces persisted quality runs, API-driven cross-session analysis, scheduled analysis, or
dataset versioning, ingestion, semantic, profiling, and quality artifacts **must** bind to one
canonical dataset-version/content digest. This is now an explicit architecture and roadmap
prerequisite rather than an informal limitation.

## CI clean-environment verification

The Linux GitHub Actions job uses Python 3.12 and runs directly, without any NumPy shim:

1. locked dependency installation;
2. Ruff format check;
3. Ruff lint/security;
4. strict mypy;
5. pre-commit across all files;
6. installed dependency compatibility;
7. full pytest with configured branch coverage and coverage gate;
8. source and wheel package build;
9. FastAPI and Streamlit smoke tests;
10. Docker Compose validation and build.

This audit added the previously absent pre-commit, dependency-compatibility, and package-build
steps. No CI control was weakened for the local Windows problem.

## Local environment status

Windows Application Control blocks the installed
`numpy/random/_common.cp312-win_amd64.pyd`. Direct pytest therefore stops during pandas import
with 18 collection errors. This is a host/runtime policy problem; no HaraLens assertion runs.

For local runtime validation only, a temporary `sitecustomize.py` supplied the three
`numpy.random` annotation types pandas imports. HaraLens source and tests do not call
`numpy.random`. The temporary directory and all audit caches/reports were removed, and a
repository search found no shim dependency.

The safest remediation is to have the machine administrator approve the official Python and
locked NumPy binaries under the existing Application Control policy, then recreate `.venv`
with `uv sync --locked` in an approved path and run plain pytest. Disabling Application
Control or changing NumPy versions without compatibility evidence is not recommended.

The package build is independently blocked locally: Hatchling is absent from the available uv
cache, while PyPI DNS access is unavailable. Clean CI now builds the package explicitly.

## Tests added/changed

The audit expands the Phase 1E focused set from 34 to 51 passing cases. Changes cover:

- four zero-population/percentage boundary cases and invalid combinations;
- failure-severity policy at draft and final-finding boundaries;
- malicious cell, column, and row mutations followed by an observing check;
- duplicate definition/configuration metadata and contradictory states;
- configuration and registry canonical ordering plus meaningful differences;
- run/finding identity changes for versions, thresholds, targets, severity, evidence, and
  framework version;
- invalid targets, empty target sets, execution budgets, and fail-fast behavior;
- serialized execution, finding, summary, dimension, metadata, and run-reference integrity;
- context version and profile-cardinality mismatch detection;
- typed framework error propagation and convenience context accessors.

No test-only check is registered in production.

## Final validation results

### Passed directly

| Validation | Result |
| --- | --- |
| Ruff lint/security | Passed |
| Ruff format check | Passed: 86 files |
| Strict mypy | Passed: 35 source files |
| Pre-commit | Passed: Ruff lint/security and format hooks |
| Dependency compatibility | Passed: all 77 installed packages compatible |
| Streamlit direct smoke | Passed: health `ok`, HTTP 200, root served HTML |
| `git diff --check` | Passed; only informational LF-to-CRLF notices |
| Shim source/artifact search | Passed: no repository dependency or temporary shim remained |

### Passed under temporary environment workaround

| Validation | Result |
| --- | --- |
| Full pytest with branch coverage | **441 passed**, 0 failed, 0 skipped; 2 unchanged dependency warnings |
| Overall statement coverage | **99.06%** (`2,427/2,450`) |
| Overall branch coverage | **98.39%** (`612/622`) |
| Overall combined coverage | **98.93%** |
| Focused Phase 1E tests | **51 passed** |
| Quality-package statement coverage | **99.20%** (`741/747`) |
| Quality-package branch coverage | **98.54%** (`203/206`) |
| Quality-package combined coverage | **99.04%** |
| FastAPI smoke | Passed: HTTP 200 with expected typed health body |
| Combined Streamlit smoke | Passed: health `ok`, HTTP 200, root served HTML |

### Blocked by host/network

| Validation | Result |
| --- | --- |
| Plain pytest | Blocked before test execution: Windows Application Control rejected NumPy `_common.pyd`; 18 collection errors |
| Local package build | Blocked: Hatchling absent from offline cache and PyPI DNS unavailable |
| Docker | Blocked: Docker CLI is not installed |

## Remaining uncovered paths

All quality modules except `runner.py` have complete statement coverage. The six remaining
runner lines and three branches are defensive paths:

- `Series.nunique` raises `TypeError`/`ValueError` while a trusted semantic artifact still
  claims a concrete unique count;
- an internally constructed column target has `column_position=None`, which `QualityTarget`
  validation already rejects;
- target sorting receives a validated column target with no position, also prevented by the
  model;
- converting a table column label to `str` raises, after upstream semantic/profiling artifacts
  for that same label were already created.

Forcing these paths would require bypassing validated models or creating contradictory trusted
artifacts. Their safe fallback/error behavior remains in place, and tests instead prioritize
reachable framework contracts.

## Known limitations

- Full dataset lineage awaits the canonical digest prerequisite described above.
- Check-specific row, regex, and combination limits remain cooperative and must be honored by
  Phase 1F implementations.
- Copy-on-write does not promise isolation for direct private-manager manipulation or in-place
  mutation of nested mutable Python objects inside object cells.
- Logical results deliberately exclude execution duration and timestamps.
- Local plain pytest, FastAPI startup, and package build require host/network remediation;
  clean Linux CI has direct coverage for all three operations.
- Docker cannot be validated on this host.

## File inventory

### Created

- `docs/PHASE_1E_PRE_FREEZE_AUDIT.md`

### Modified

- `.github/workflows/ci.yml`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/PHASE_1E_REPORT.md`
- `docs/QUALITY_FRAMEWORK.md`
- `docs/ROADMAP.md`
- `src/haralens/quality/models.py`
- `src/haralens/quality/runner.py`
- `tests/unit/test_quality_models_and_registry.py`
- `tests/unit/test_quality_runner.py`

No file was deleted. No dependency or lockfile changed. Phase 1F was not started.
