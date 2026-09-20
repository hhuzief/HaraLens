# HaraLens v0.1 — Release Candidate Verification Report

## Executive summary

Gate 4 hardened the release candidate without adding external services. The application now has
safe deterministic insight identifiers, sidebar-first result navigation, a package-version
fallback that keeps FastAPI healthy in editable environments, safe report filenames, deployment
documentation, and a concrete release checklist.

## Release architecture

Streamlit is the public v0.1 presentation host. It uses one session-scoped `AnalysisResult` from
`haralens.application`; analytics, readiness, insights, scoring, quality, profiling, ingestion,
and report generation remain reusable modules under `src/haralens`. No database is required.

## Navigation

Before analysis: Home, Analyze, Methodology / About.

After analysis: Home, Analyze, Overview, Data Quality, AI Readiness, Explore, Columns,
Recommendations, Methodology / About. Result pages guard missing state with a clear “No active
analysis” message. Reset removes the result, target, worksheet, filter, and explorer state.

## Runtime and privacy hardening

- Insight IDs use one Unicode-normalizing, uppercase, punctuation-safe canonicalizer.
- Generated IDs include deterministic SHA-256 suffixes to prevent collisions between normalized
  column names and relationship pairs.
- IDs never include cell values.
- Reports are generated in memory and use sanitized download filenames.
- Reports contain no raw rows or raw identifier values.
- Uploads are processed by the HaraLens server for the current session and are not intentionally
  persisted in an application database. Users must upload data they are authorized to process.

## Validation

- Full pytest: **460 passed**
- Coverage: **97.31%** branch-enabled coverage
- Focused Gate 4/runtime tests: passed
- Ruff lint/security: passed
- Ruff format: passed
- Strict mypy (`src apps`): passed
- Pre-commit: passed using a workspace-local hook cache
- Package build (`uv build --offline`): passed
- FastAPI and Streamlit smoke: passed; health/root responses were HTTP 200
- Exact locked Streamlit launch: passed
- Docker validation/build: unavailable because Docker is not installed
- `uv pip check`: reports the existing local editable distribution as incomplete because its
  metadata file is unreadable; this is a local environment defect, not a dependency conflict.

## Performance measurements

| Stage | Small | 10k × 50 |
|---|---:|---:|
| Complete analysis pipeline | 0.084 s | 10.783 s |

Exact engine statistics remain distinct from bounded chart samples (maximum 5,000 points per
visualization). Correlation analysis is bounded to 40 numeric columns.

## Release classification

- **P0:** none identified in application behavior.
- **P1:** Docker and clean dependency-environment validation require a host with Docker and a
  healthy editable environment before public deployment.
- **P2:** HTML is the primary report artifact; PDF export is deferred to a later release.
- **P3:** authentication, persistence, model training, hosted AI, and cloud connectors remain
  future work.

## Recommendation

**NOT READY FOR PUBLIC DEPLOYMENT** until Docker/clean-environment validation is completed on a
deployment-capable host. The application workflow and automated validation are otherwise release
candidate ready.
