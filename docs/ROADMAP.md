# Roadmap

Gate 1 is the latest completed slice. Later product integration phases remain planned.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Product and architecture foundation | Implemented; see verification report |
| 1A | Ingestion contract and bounded CSV loading | Implemented; see verification report |
| 1B | Bounded Excel and Parquet ingestion | Implemented; see verification report |
| 1C | Explainable semantic type inference | Implemented; see verification report |
| 1D | Dataset and column profiling | Implemented; see verification report |
| 1E | Typed data-quality check framework | Implemented; see verification report |
| Gate 1 | Production checks, explainable scoring, deterministic recommendations | Implemented |
| 2 | Professional Streamlit workflows | Planned |
| 3 | Authentication and SaaS persistence | Planned |
| 4 | Versioned analysis API and service integration | Planned |
| 5 | Advanced analytics | Planned |
| 6 | ML readiness | Planned |
| 7 | ML workbench | Planned |
| 8 | Optional local AI | Planned |
| 9 | Reporting and governance | Planned |
| 10 | Automation | Planned |
| 11 | Additional data connectors | Planned |
| 12 | Advanced analytical modules | Planned |
| 13 | Production hardening | Planned |

Gate 2 product integration, repair, UI, persistence, reporting, ML, and AI remain later work.

Architecture prerequisite: before persisted quality runs, API-driven cross-session analysis,
scheduled analysis, or dataset versioning, bind ingestion, semantic, profiling, and quality
artifacts to one canonical dataset-version/content digest.
