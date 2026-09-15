# Development

## Install

Use uv 0.11.2 (the version used for the lockfile) and Python 3.12. `uv sync --locked`
installs the application and development tools in `.venv`, downloading Python when
needed. No global pip install is required. Commit `uv.lock` for reproducibility.

On restricted Windows machines, keep uv-managed files inside the repository:

```powershell
$env:UV_CACHE_DIR = "$PWD\.uv-cache"
$env:UV_PYTHON_INSTALL_DIR = "$PWD\.uv-python"
uv python install 3.12 --no-bin
uv sync --locked
```

These environment variables apply to the current terminal. Set them in each new
terminal when using this local Python installation. Both directories are ignored.

Optional: copy `.env.example` to `.env`. Valid environment values are development,
test, production; log levels are DEBUG, INFO, WARNING, ERROR, CRITICAL. Invalid
values and nonpositive ingestion limits fail validation. Default CSV limits are
10 MiB, 100,000 data rows and 1,000 columns. Keep secrets out of source control.

## Start

Run from the repository root in two terminals:

```powershell
uv run --locked uvicorn apps.api.main:app --host 127.0.0.1 --port 8000 --no-access-log
uv run --locked streamlit run apps/streamlit/app.py --server.address=127.0.0.1 --server.headless=true --browser.gatherUsageStats=false
```

API health is `/api/v1/health`; Swagger UI is `/docs`. The static UI on port 8501
starts independently of the API. Use Ctrl+C to stop each server. No external
telemetry is needed; Streamlit usage statistics are disabled in these commands.

## Checks

```powershell
uv run --locked pytest
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked mypy
uv run --locked python scripts/smoke.py
uv run --locked pre-commit install
```

Ruff includes Bandit-derived S security rules. Tests include coverage (minimum 85%)
for implemented package behavior; Protocol declarations are excluded. The smoke
script uses temporary free ports, saves startup logs under ignored `.smoke`, and
stops only its own processes. AppTest verifies actual Streamlit script execution;
HTTP startup alone cannot verify that a Streamlit page executes successfully.

CI runs lint, formatting, type checks, all tests/coverage, HTTP smoke checks and
container configuration/builds. Integration/security/performance tests will be
added with the workflows they verify. Install hooks locally if desired; CI checks
are authoritative and do not depend on hooks being installed.

## Docker foundation

With Docker Engine and Compose installed:

```powershell
docker compose config --quiet
docker compose up --build
```

The shared Dockerfile provides both services and runs as a non-root user. Only
loopback ports are published. No database or Ollama containers are needed in this
phase. Use `docker compose down` to stop. Image tags are pinned to a Python minor
version and uv version, but not immutable digests; production hardening is deferred.

## Contributions and limitations

Keep changes phase-scoped. Update tests and docs with behavior changes. Run every
check before submitting. Do not add unused dependencies or fake analytical outputs.
The full product specification describes the destination, not delivered features.
CSV ingestion is a package API in Phase 1A; there is no upload UI or HTTP ingestion
endpoint. See [INGESTION.md](INGESTION.md) for usage and policies.
