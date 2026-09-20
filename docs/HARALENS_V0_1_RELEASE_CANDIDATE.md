# HaraLens v0.1 release candidate

HaraLens is a deterministic tabular-data understanding application for CSV, XLSX, and Parquet.
It provides bounded ingestion, semantic inference, descriptive profiling, six-dimensional data
health diagnostics, AI-readiness assessment, deterministic insights, recommendations, and an
in-memory HTML report.

The release architecture keeps the Streamlit UI as presentation and places orchestration and
analytics under `src/haralens`. The anonymous workflow requires no database. Uploaded datasets
are processed by the server for the active session and are not intentionally persisted in an
application database.

AI Readiness is a technical preparation signal. It does not establish label quality, causal
validity, fairness, sampling representativeness, or expected model performance. Correlations are
descriptive and do not imply causation; potential outliers are not automatically errors.

Known v0.1 limitations are documented in [DEPLOYMENT.md](DEPLOYMENT.md) and the release checklist.
