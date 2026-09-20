# HaraLens v0.1 — Gate 1 Intelligence Engine Verification Report

> Superseded by the final calibration audit: [HARALENS_GATE_1_FINAL_CALIBRATION_REPORT.md](HARALENS_GATE_1_FINAL_CALIBRATION_REPORT.md).

## Executive summary

Gate 1 adds an explicit production quality catalogue, a separate explainable health scorer, and
a deterministic non-destructive recommendation engine. The implementation preserves the Phase 1E
runner and contracts, contains no UI/API/persistence/AI integration, and does not commit or push.

## Repository state before implementation

The repository began clean on `main` at commit `54ae0b7` (`feat: add data quality check framework`),
with the Phase 1E registry intentionally empty. Existing ingestion, semantic, profiling, and
quality tests were green. `pyproject.toml`, `uv.lock`, CI, and the Phase 1E contracts were reviewed
before implementation.

## Production quality catalogue

`create_default_quality_registry()` returns eleven sorted checks, all version `1.0.0`:

| Check ID | Dimension | Scope | Applicability / denominator |
|---|---|---|---|
| DQ_COMPLETENESS_DATASET_MISSINGNESS | completeness | dataset | all tables; total cells |
| DQ_COMPLETENESS_COLUMN_MISSINGNESS | completeness | column | total rows |
| DQ_COMPLETENESS_EMPTY_COLUMN | completeness | column | all-null columns; total rows |
| DQ_UNIQUENESS_DUPLICATE_ROWS | uniqueness | dataset | all tables; total rows, occurrences beyond first |
| DQ_UNIQUENESS_IDENTIFIER_VALUES | uniqueness | column | effective identifier; non-null rows |
| DQ_VALIDITY_NONFINITE_NUMERIC | validity | dataset | numeric cells; infinities only |
| DQ_CONSISTENCY_COLUMN_NAME_WHITESPACE | consistency | dataset | labels; column-label count |
| DQ_CONSISTENCY_CATEGORY_NORMALIZATION | consistency | column | categorical columns; collision count |
| DQ_INTEGRITY_IDENTIFIER_MISSINGNESS | integrity | column | effective identifier; total rows |
| DQ_READINESS_CONSTANT_COLUMN | analytical_readiness | column | observed values |
| DQ_READINESS_HIGH_CARDINALITY | analytical_readiness | column | categorical non-identifiers |

Detailed methodology and thresholds are in [QUALITY_CHECKS.md](QUALITY_CHECKS.md). All findings
use typed counts/percentages, safe messages, and no raw values.

## Quality thresholds

Missingness defaults are 0% pass, >0–5% low, >5–20% medium, >20–40% high, and >40% critical.
High-cardinality ratio is 0.90; near-unique configuration is 0.95; category collision minimum is
2. Configuration is immutable, validated, versioned, and fingerprinted.

## Double-counting policy

Each finding carries a `finding_family` methodology value. Scoring deduplicates by dimension,
family, and target and retains the largest contribution. Thus a readiness symptom cannot multiply
the same family penalty for one target. Completeness and integrity remain separate dimensions and
are intentionally visible; their weighted contributions are explicit.

## Health scoring architecture

`haralens.scoring.HealthScorer` consumes only `QualityRunResult`. It never rescans a DataFrame or
creates new findings. `DimensionHealthScore` records state, score, effective weight, and every
bounded `PenaltyContribution`.

## Exact scoring formula

Severity bases are low `.05`, medium `.12`, high `.20`, critical `.35`. Let `p` be affected
prevalence in `[0,1]`; structural findings without a denominator use `p=1`. Each unique finding
penalty is:

`penalty_points = 100 × severity_base × (0.25 + 0.75 × p)`

`dimension_score = max(0, 100 − min(100, Σ penalty_points))`

The overall score is the weighted sum of evaluated dimension scores after renormalizing the
configured weights over evaluated dimensions. All outputs are bounded `[0,100]`, finite, and
deterministic.

## Dimension weights and unevaluated behavior

Defaults are completeness `.20`, uniqueness `.15`, validity `.20`, consistency `.15`, integrity
`.20`, analytical readiness `.10`. A dimension with no evaluated execution is `NOT_EVALUATED`,
has `score=null`, and contributes no weight. It is never assigned a fabricated 100 or 0.

## Interpretation bands

Excellent 90–100; good 75–<90; needs_attention 60–<75; poor 40–<60; critical 0–<40. These are
HaraLens product labels, not universal scientific claims.

## Recommendation architecture

`RecommendationEngine` maps finding families to safe investigation actions. Recommendations retain
all source finding IDs, group by family/target/dimension, and never delete, impute, mutate, or
rewrite data. Priority is severity-derived: critical urgent, high high, medium medium, low low.

## Golden dataset results

For a deterministic table containing duplicate identifiers, missing identifier, infinity,
category-format collision, duplicate row, and constant column, the chain produced **6 findings**,
an overall score of **91.8125**, and **6 deduplicated recommendations**. No raw identifier or
category value appeared in serialized output.

## Clean dataset results

For a representative all-unique, finite, non-constant table, the chain produced **0 findings**,
an overall score of **100.0**, and no recommendations. Evaluated dimensions remain explicitly
evaluated; any dimension with no applicable execution remains unevaluated.

## Pathological dataset results

Zero-row/all-null input preserves Phase 1E null-percentage semantics and produced bounded scores
without division-by-zero. Infinities, duplicate rows, identifier nulls, and category collisions
were handled by dedicated checks.

## Performance sanity

A 10,000-row × 50-column finite table completed semantic inference, profiling, quality checks,
scoring, and recommendations in approximately **3.984 seconds** on the local Windows host. The
main scans are profiling, duplicate detection, and per-column missingness; no sampling is hidden
as exact measurement.

## Determinism and serialization

Equivalent DataFrames produced equal quality, score, and recommendation models, including stable
ordering and IDs. Pydantic models are frozen, strict, finite-only, and JSON serializable. Results
contain no DataFrames, arbitrary objects, NaN, or infinity.

## Tests added

`tests/unit/test_gate1_intelligence.py` covers catalogue registration, six-dimension coverage,
golden-chain determinism/privacy, unevaluated dimensions, and monotonic missingness scoring.

## Full validation results

- Full pytest: **445 passed**, 2 dependency deprecation warnings.
- Ruff lint/security: passed.
- Ruff format: passed.
- Strict mypy: passed, 52 source files.
- Pre-commit: passed (Ruff lint/security and format hooks).
- Dependency compatibility: passed, 77 packages.
- FastAPI and Streamlit smoke: passed.
- `git diff --check`: passed, with normal CRLF conversion warnings.
- Package build: blocked locally because Hatchling was absent from the offline cache and network
  access was unavailable.
- Docker validation: not run; Docker is unavailable on this host.

The full test run passed directly on this host. The temporary NumPy shim was used only for the
standalone performance probe and was removed; it is not repository source or CI configuration.

## Coverage

The full run reported **96.22% combined coverage** (2,744/2,842 statements and 684/702 branches
covered, with the configured 85% gate satisfied). New scoring and recommendation models are fully
covered by the integration path; remaining misses are defensive runner/catalogue branches.

## Files created

- `src/haralens/quality/checks/` catalogue and configuration modules
- `src/haralens/scoring/`
- `src/haralens/recommendations/`
- `tests/unit/test_gate1_intelligence.py`
- `docs/QUALITY_CHECKS.md`
- `docs/HEALTH_SCORING.md`
- `docs/RECOMMENDATIONS.md`
- `docs/HARALENS_V0_1_RELEASE.md`
- `docs/HARALENS_GATE_1_VERIFICATION_REPORT.md`

## Files modified

- `src/haralens/quality/__init__.py`
- `README.md`
- `docs/ARCHITECTURE.md`
- `docs/ROADMAP.md`

## Known limitations

No relational metadata exists, so foreign-key integrity and domain-specific validity are not
claimed. Category normalization is conservative and reports counts only. Resource limits remain
those of the Phase 1E runner. Gate 2 product orchestration, persistence, UI workflows, and
dataset-version lineage are intentionally outside this gate.

## Errors encountered and resolutions

Initial linting caught import ordering and line-length issues in the new modules; Ruff formatting
and targeted edits resolved them. The first focused-only test command failed the repository-wide
coverage threshold because it intentionally omitted the existing suite; the focused tests passed
when run with `--no-cov`. The full suite then passed. Offline package build remains an environment
blocker rather than a HaraLens test failure.

## Gate 2 integration API

```python
from haralens.quality import (
    QualityCheckContext,
    QualityCheckRunner,
    QualityFrameworkConfig,
    create_default_quality_registry,
)
from haralens.scoring import HealthScorer
from haralens.recommendations import RecommendationEngine

registry = create_default_quality_registry()
quality = QualityCheckRunner().run(context, registry, QualityFrameworkConfig())
health = HealthScorer().score(quality)
recommendations = RecommendationEngine().generate(quality, health)
```

## Git diff summary

The change adds the three engine packages, their strict models/configuration, production tests,
and methodology documentation; it modifies only public exports and project documentation. No
dependency or lockfile changed. No commit or push was performed.

## Recommendation

Gate 1 is ready for its pre-release audit. Gate 2 has not been implemented.
