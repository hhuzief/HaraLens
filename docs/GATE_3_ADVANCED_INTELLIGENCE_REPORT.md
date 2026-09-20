# HaraLens v0.1 — Gate 3 Advanced Intelligence Verification Report

## Executive summary

Gate 3 adds reusable, deterministic analytics, AI-readiness assessment, structured insights,
target diagnostics, and a raw-row-free HTML report. Streamlit only renders typed results from
`haralens.analytics`, `haralens.readiness`, `haralens.insights`, and `haralens.reporting`.

## Readiness methodology

The score is a weighted technical preparation signal, not a model-performance prediction:

| Dimension | Weight | Measurement |
|---|---:|---|
| Data sufficiency | 15% | rows, with a conservative advisory curve capped at 1000 rows |
| Data completeness | 20% | 100 minus exact missing-cell percentage |
| Feature usability | 20% | supported candidate semantic columns divided by total columns |
| Type readiness | 15% | unsupported/ambiguous semantic columns reduce the score |
| Cardinality risk | 10% | categorical columns above `max(20, 50% of non-null rows)` |
| Distribution risk | 10% | numeric columns containing IQR potential outliers |
| Data integrity | 10% | duplicate-row percentage as a neutral technical signal |

Overall score is the weighted sum, rounded to three decimals and bounded to 0–100. Bands are:
`Highly ready` (90–100), `Ready` (75–<90), `Preparation recommended` (60–<75), `Significant
preparation required` (40–<60), and `Not ready` (<40). These labels are methodology labels,
not universal scientific claims.

The engine cannot determine whether labels are meaningful, collection is unbiased, the dataset
represents deployment data, or a relationship is causal. Selected targets are optional and are
classified conservatively as classification or regression candidates; no model is trained.

## Advanced analytics

Numeric outliers use `Q1 - 1.5*IQR` and `Q3 + 1.5*IQR`; they are described as potential outliers.
Pearson correlation uses finite, pairwise-complete observations, skips constants and pairs with
fewer than two usable observations, and is bounded to 40 numeric columns. Strong relationships
use `abs(r) >= 0.8` and explicitly do not imply causation. Distribution language uses absolute
skewness thresholds of `<0.5`, `<1.0`, and `>=1.0` for approximately symmetric, moderately
skewed, and strongly skewed. Exact profile statistics remain the source of truth.

## Insights and reporting

Insights are deterministic, capped at eight by default, and ranked by importance then stable ID.
The report is reusable HTML because no PDF dependency was already available; it contains no raw
rows or category values. The local AI boundary is represented by structured result contracts;
no LLM or paid API is required or invoked.

## Validation

Gate 3 focused tests: **5 passed**. Full suite: **456 passed, 2 environment failures** caused by
the local editable distribution reporting package version `None` to FastAPI. Coverage was
**97.14%**. Ruff lint and format checks passed; strict mypy passed for `src apps`. Streamlit smoke
served HTTP 200. Package build and pre-commit remain blocked by the unavailable offline Hatchling
and hook environments. No commit or push was performed.

