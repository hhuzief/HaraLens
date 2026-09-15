# Roadmap

Only Phase 0 is authorized for this implementation.

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Product and architecture foundation | Implemented; see verification report |
| 1 | Core tabular ingestion, profiling, quality, scoring, recommendations | Planned |
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

Next Phase 1 task, only after authorization: define the ingestion contract and
resource-limit policy, then implement bounded CSV loading with synthetic fixtures
and tests for valid input, invalid encoding, malformed rows and size limits.
Excel/Parquet, type inference, profiling and the remaining engine follow incrementally.
