# Security

Phase 0 exposes only process health and a static application shell. Authentication,
authorization, uploads, database access, and tenant isolation are not implemented.
Use local loopback bindings; this foundation is not a production SaaS deployment.

Do not commit `.env`, tokens, datasets, or Streamlit secrets. Application logs use
fixed event names and must never include credentials or raw data. The JSON formatter
does not sanitize arbitrary messages; callers are responsible for safe event content.
Uvicorn access logging is disabled in documented commands to avoid query-string logs.

Future adapters must validate identity, enforce tenant ownership on every operation,
and include cross-tenant tests before release. Domain organization IDs and Protocols
are contracts, not implemented authorization controls.

Report vulnerabilities privately to the repository maintainer through GitHub private
vulnerability reporting if enabled. Do not post sensitive evidence in public issues.
