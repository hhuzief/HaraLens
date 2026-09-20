# HaraLens v0.1 deployment

## Runtime

Use Python 3.12–3.13 with the locked `uv` environment. The public v0.1 workflow is the
Streamlit application; FastAPI remains a health-capable architectural foundation.

```powershell
uv sync --locked
uv run --locked streamlit run apps/streamlit/app.py
```

The process binds Streamlit's configured port (8501 by default). No database or persistent
storage is required for anonymous analysis. Uploaded data is processed by the HaraLens server,
kept in the current Streamlit session, and is not intentionally persisted in an application
database. Users must upload only data they are authorized to process.

## Configuration and limits

`HARALENS_` settings control ingestion byte, row, column, archive, worksheet, metadata, and
row-group limits. Do not commit `.env` or secrets. Configure the deployment platform's port and
resource limits rather than changing application code.

## Operational checks

The FastAPI foundation exposes `/health`; Streamlit is checked by its HTTP root response and
application smoke tests. Reports are generated in memory and are returned as downloads; no shared
temporary report path is used.

Docker is optional and was not available in the current validation environment.

## Streamlit Community Cloud

- **Repository:** the HaraLens GitHub repository
- **Branch:** `main`
- **Entrypoint:** `apps/streamlit/app.py`
- **Python:** 3.12
- **Dependencies:** `pyproject.toml` and the committed `uv.lock`; no separate
  `requirements.txt` is required
- **Secrets:** none required for the anonymous v0.1 workflow; do not configure Supabase,
  OpenAI, Ollama, database credentials, or API keys for core startup
- **Resource expectations:** uploads remain bounded at 10 MiB, 100,000 rows, and 1,000 columns;
  XLSX, Parquet, correlation, and visualization limits remain enforced by the engine

Verify a deployment by opening the app, analyzing the bundled synthetic CSVs, checking the
sidebar result pages, downloading an HTML report, and using **Analyze another dataset**. Roll back
by selecting the previous known-good `main` commit in Community Cloud and redeploying; no database
migration or persistent-data rollback is required for v0.1.
