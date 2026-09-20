# HaraLens

Intelligent Data Health, Analytics & ML Readiness Platform.

Understand, validate and improve your data before trusting the decisions or models
built from it. **Phase 1E's deterministic data-quality check framework is implemented.**

| Capability | Status |
| --- | --- |
| Package, configuration, JSON application logging | Implemented |
| Typed metadata models and infrastructure contracts | Implemented |
| FastAPI liveness endpoint and minimal Streamlit shell | Implemented |
| Tests, checks, CI definition, Docker foundations | Implemented |
| Bounded UTF-8 CSV ingestion through a reusable contract | Implemented — Phase 1A |
| Bounded macro-free XLSX and flat Parquet ingestion | Implemented — Phase 1B |
| Explainable semantic type inference | Implemented — Phase 1C |
| Semantic-aware dataset and column profiling | Implemented — Phase 1D |
| Typed quality-check framework and runner | Implemented — Phase 1E |
| Production quality checks, scoring and recommendations | Implemented — v0.1 Gate 1 |
| Authentication, persistence, advanced analytics, ML and AI | Planned |

## Quick start

Install uv, then run from the repository root:

```powershell
uv sync --locked
uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --no-access-log
```

In another terminal:

```powershell
uv run --locked streamlit run apps/streamlit/app.py --server.address=127.0.0.1 --server.headless=true --browser.gatherUsageStats=false
```

Open http://127.0.0.1:8501. Health: http://127.0.0.1:8000/api/v1/health.
OpenAPI documentation: http://127.0.0.1:8000/docs.
No database, account, paid API, or Ollama instance is required.

## Verification

```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python scripts/smoke.py
```

See [development instructions](docs/DEVELOPMENT.md) for local cache settings,
containers, configuration, and pre-commit setup.

## Architecture and scope

Streamlit → FastAPI → application services → engines → storage adapters.
Phase 0 provides the two entry points and domain boundaries. The static UI does
not yet call the backend. No uploads, analysis, authentication or persistence exist.

- [Product specification](docs/PRODUCT_SPEC.md): full future scope, not current features.
- [Architecture](docs/ARCHITECTURE.md)
- [Bounded ingestion](docs/INGESTION.md)
- [Semantic type inference](docs/SEMANTIC_INFERENCE.md)
- [Dataset and column profiling](docs/PROFILING.md)
- [Quality-check framework](docs/QUALITY_FRAMEWORK.md)
- [Production quality checks](docs/QUALITY_CHECKS.md)
- [Health scoring](docs/HEALTH_SCORING.md)
- [Recommendations](docs/RECOMMENDATIONS.md)
- [v0.1 release boundary](docs/HARALENS_V0_1_RELEASE.md)
- [Gate 1 final calibration audit](docs/HARALENS_GATE_1_FINAL_CALIBRATION_REPORT.md)
- [Roadmap](docs/ROADMAP.md)
- [Proposed scoring methodology](docs/SCORING_METHODOLOGY.md)
- [Phase 0 verification report](docs/PHASE_0_REPORT.md)
- [Phase 1A verification report](docs/PHASE_1A_REPORT.md)
- [Phase 1B verification report](docs/PHASE_1B_REPORT.md)
- [Phase 1C verification report](docs/PHASE_1C_REPORT.md)
- [Phase 1D verification report](docs/PHASE_1D_REPORT.md)
- [Phase 1D pre-freeze profiling audit](docs/PHASE_1D_PRE_FREEZE_AUDIT.md)
- [Phase 1E verification report](docs/PHASE_1E_REPORT.md)
- [Phase 1E pre-freeze framework audit](docs/PHASE_1E_PRE_FREEZE_AUDIT.md)
- [Security](SECURITY.md)

MIT licensed. Docker foundations need Docker Engine to build and run; local
verification limitations are recorded in the Phase 0 report.
