# Architecture

## Status and boundaries

Phase 1A adds bounded CSV ingestion to the foundation. It is not a deployed
analytics service.

```text
apps/streamlit/app.py  (static presentation shell)
          ↓ future HTTP service client
apps/api/main.py → haralens.api (FastAPI composition and health router)
          ↓ future application services
haralens.domain (immutable typed metadata and infrastructure Protocols)
haralens.ingestion (typed contracts → bounded CSV adapter → pandas DataFrame)
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
Pandas is the sole Phase 1A table engine because it is mature, integrates directly
with planned analytics, and avoids premature multi-engine complexity. The dependency
is now explicit rather than relied on through Streamlit.

The CSV adapter validates the byte limit before decoding, strictly decodes UTF-8,
validates structure and hard row/column limits before constructing the DataFrame,
and never truncates or skips malformed rows. See [ingestion](INGESTION.md).

## Configuration and operation

Settings load defaults, optional `.env`, then `HARALENS_` environment overrides.
Environment, log level and ingestion hard limits are configured; no placeholder credentials.
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

Unit tests cover config validation, model invariants and JSON logging. API tests use
FastAPI TestClient. Streamlit AppTest executes the page and a rerun. The smoke script
starts real HTTP servers, polls their health routes, checks the served frontend,
and always terminates its own processes. CI runs all checks plus container builds.
Integration, security and performance test areas are reserved for real adapters and
engines; there are no placeholder passing tests for unimplemented features.

## Official references consulted

- [Streamlit navigation](https://docs.streamlit.io/develop/api-reference/navigation/st.navigation)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
- [uv Docker integration](https://docs.astral.sh/uv/guides/integration/docker/)
