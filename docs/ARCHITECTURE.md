# Architecture

## Status and boundaries

Phase 1C adds deterministic semantic type inference after bounded ingestion. It remains a
reusable engine rather than a deployed analytics service.

```text
apps/streamlit/app.py  (static presentation shell)
          ↓ future HTTP service client
apps/api/main.py → haralens.api (FastAPI composition and health router)
          ↓ future application services
haralens.domain (immutable typed metadata and infrastructure Protocols)
haralens.ingestion (typed contracts → bounded format adapters → pandas DataFrame)
haralens.semantic (physical dtype + explainable rules → versioned semantic profile)
          ↓ future adapter implementations
PostgreSQL / Supabase authentication / object storage
```

`src/haralens/common` owns validated settings and JSON application logging.
Domain modules import neither FastAPI nor Streamlit. Concrete adapters will depend
on domain contracts; domain logic will not depend on vendor SDKs. `apps` contains
launchers; the wheel contains the reusable `haralens` package. Python 3.12 is the
local/CI baseline; package support is limited to 3.12–3.13.

## Models and interfaces

Initial models: User, Organization, Workspace, Project, Dataset, DatasetVersion,
and AccessContext. Entities have UUIDs and timezone-aware creation times. Dataset
versions identify content using a SHA-256 digest. Frozen models prevent accidental
mutation; changes should create a new validated value. Persistence adapters will
own update timestamps and enforce relational consistency.

AuthenticationProvider, ProjectRepository, and ObjectStorage are typed contracts.
Authentication must verify credentials and organization membership server-side.
Repository/storage operations receive trusted access context and must enforce
ownership. These contracts do not provide working authentication or authorization.
There are no adapters or database migrations yet.

Implement additional domain/result models alongside their actual use cases rather
than freezing speculative schemas for the entire roadmap. The ingestion contract
accepts caller-owned bytes and returns a pandas DataFrame with serializable metadata.
Pandas remains the common table representation because it integrates directly
with planned analytics, and avoids premature multi-engine complexity. The dependency
is explicit rather than relied on through Streamlit. CSV uses the standard parser plus
pandas, XLSX uses `openpyxl` with `defusedxml`, and Parquet uses PyArrow.

The CSV adapter validates the byte limit before decoding, strictly decodes UTF-8,
validates structure and hard row/column limits before constructing the DataFrame,
and never truncates or skips malformed rows. See [ingestion](INGESTION.md).

The binary adapters keep the same request/result/error vocabulary. An optional exact
worksheet name is the only format-specific request field. Serializable metadata carries
the selected worksheet for XLSX or schema/row-group information for Parquet. XLSX archive
validation runs before lazy workbook parsing; Parquet footer metadata supplies dimensions
before full table construction. Every adapter verifies the final DataFrame dimensions and
column order against the format-specific validation result.

`haralens.semantic` accepts either that ingestion result or a caller-owned pandas DataFrame.
It computes exact non-null and uniqueness metrics, uses bounded deterministic content
inspection, and returns immutable Pydantic results with separate physical and semantic types,
evidence codes, confidence, warnings, alternatives, and an override extension point. The
dataset service isolates a pathological column as `unknown` so later columns still run.
Inference imports neither presentation framework and does not perform broader profiling.
See [semantic inference](SEMANTIC_INFERENCE.md).

## Configuration and operation

Settings load defaults, optional `.env`, then `HARALENS_` environment overrides.
Environment, log level and ingestion hard limits are configured; no placeholder credentials.
Semantic thresholds live in the strict, immutable `SemanticInferenceConfig` passed directly
to the reusable service, so identical table/configuration/version inputs remain reproducible.
Settings are created at the composition root rather than as a global singleton.
Logging starts in FastAPI lifespan; imports do not configure root logging.
Application logs are UTC JSON events. Third-party server logs keep their own format.
Do not put sensitive data in log messages. Correlation IDs will accompany real
request/run workflows in later phases.

`GET /api/v1/health` returns typed process liveness. It does not assert database,
AI, or storage readiness. OpenAPI describes the contract. No readiness route is
needed until dependencies exist. Only this public, data-free API route exists.

## Future architecture decisions

- Keep statistics, data access, and business rules out of Streamlit callbacks.
- Application services coordinate domain engines and injected infrastructure ports.
- PostgreSQL migrations and Supabase adapters arrive in Phase 3, with tenant tests.
- Preserve originals, version datasets, and scope persisted resources by ownership.
- Compute deterministic results before rules and optional LLM interpretation.
- Ollama will be optional and receive aggregate findings by default.
- Resource-aware engines must bound file size, memory, sampling and work duration.
- Add typed failures, safe API error mapping, correlation IDs and background jobs
  when their workflows exist; do not claim these controls are already implemented.

## Validation

Unit tests cover config validation, model invariants, JSON logging, all three ingestion
adapters, and the semantic rule engine. Golden business tables, conflict cases, threshold
boundaries, serialization, deterministic sampling, immutability, and failure isolation test
the semantic contract. In-memory workbook and Parquet fixtures exercise security and
boundary cases without Microsoft Excel or network access. Bounded performance tests
guard against catastrophic ingestion regressions. API tests use FastAPI TestClient.
Streamlit AppTest executes the page and a rerun. The smoke script starts real HTTP
servers, polls their health routes, checks the served frontend, and always terminates
its own processes. CI runs all checks plus container builds.

## Official references consulted

- [Streamlit navigation](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
- [openpyxl optimized read mode](https://openpyxl.readthedocs.io/en/stable/optimized.html)
- [openpyxl formula and link loading options](https://openpyxl.readthedocs.io/en/stable/api/openpyxl.reader.excel.html)
- [openpyxl XML security guidance](https://openpyxl.readthedocs.io/en/stable/#security)
- [PyArrow ParquetFile metadata-first reader](https://arrow.apache.org/docs/python/generated/pyarrow.parquet.ParquetFile.html)
- [Python ZIP archive APIs](https://docs.python.org/3/library/zipfile.html)
