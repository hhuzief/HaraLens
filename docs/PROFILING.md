# Dataset and column profiling

## Scope and guarantee

HaraLens Phase 1D turns a bounded table and its matching semantic inference result into an
immutable, JSON-serializable `DatasetProfile`. The engine is independent of FastAPI,
Streamlit, persistence, visualization, scoring, quality rules, machine learning, and AI.

Profiling describes observed data. It does not label a result healthy, poor, severe,
critical, anomalous, or invalid. It does not recommend a treatment.

Given the same table, semantic profile, profiling configuration, and profile version, the
service returns the same result. Phase 1D scans all accepted rows; it does not sample.

## Public API

```python
from haralens.profiling import profile_dataset
from haralens.semantic import infer_semantic_types

semantic_profile = infer_semantic_types(ingestion_result)
dataset_profile = profile_dataset(ingestion_result, semantic_profile)
payload = dataset_profile.model_dump(mode="json")
```

`ProfilingService.profile()` and `profile_dataset()` accept either a pandas `DataFrame` or an
`IngestionResult`, plus a `DatasetSemanticProfile`. The source and semantic result are
separate parameters so profiling cannot silently infer types again or hide a stale contract.

Before doing statistical work, the service verifies:

- ingestion result dimensions still match its table;
- table size is within the profiling resource policy;
- semantic dataset dimensions and number of columns match;
- every semantic column has the same position, safe name, physical dtype, total/null counts,
  and exact distinct count as the current table.

A mismatch raises a safe `ProfilingError` with a stable `ProfilingErrorCode`. This catches
common table mutation and wrong-profile mistakes. It cannot prove that values are unchanged
when all checked structure and counts happen to remain equal; callers should treat a semantic
profile and table as one immutable analysis input.

## Result hierarchy

```text
DatasetProfile
├── DatasetSummary
├── ColumnProfile[]
│   └── NumericStatistics | CategoricalStatistics
│       | DatetimeStatistics | TextStatistics | None
├── ProfilingConfig
├── ProfilingRunMetadata
└── ProfileWarning[]
```

All result/config models are strict, frozen Pydantic models with unknown fields forbidden.
The profile format version is `1.0.0`; the semantic inference version used by the run is also
recorded.

## Dataset summary

`DatasetSummary` contains exact row, column, and cell counts; deep pandas memory footprint;
missing-cell count and percentage; duplicate-row count and percentage; effective semantic
type distribution; and empty, constant, and identifier column counts.

Duplicate rows mean repetitions after the first occurrence, matching
`DataFrame.duplicated(keep="first")`. The percentage denominator is the row count. Missing
percentage uses all cells. A zero denominator produces `0.0`, so empty tables serialize
without undefined numbers. If non-tabular direct-DataFrame objects cannot be compared,
duplicate fields become `null` with `DUPLICATE_COUNT_UNAVAILABLE` instead of a fabricated
count.

Memory footprint uses pandas deep memory accounting and includes the DataFrame index. Each
column separately reports deep memory excluding the shared index.

## Common column facts

Every `ColumnProfile` preserves physical position and order and contains:

- safe column name and physical dtype;
- inferred and effective semantic types plus inference confidence;
- total, null, and non-null counts;
- missing percentage;
- exact distinct count and cardinality ratio when values can be compared;
- deep memory bytes;
- one type-appropriate statistics object, when applicable;
- typed operational warnings.

The effective semantic type honors the Phase 1C `user_confirmed_type` extension. Summary type
counts and specialized-statistic selection use that effective type; the original inferred
type remains visible.

## Numeric statistics

Numeric and physically numeric constant columns report:

- finite, non-numeric, positive-infinity, and negative-infinity counts;
- negative, zero, and positive finite counts;
- minimum, maximum, mean, median;
- standard deviation and variance;
- first and third quartiles and interquartile range;
- skewness and excess kurtosis.

Finite aggregates use only non-null, numeric values for which `isfinite` is true. `NaN` is a
null under the pandas table contract and contributes to the column null count. Positive and
negative infinity are non-null but are excluded from every aggregate and counted separately.
Non-null values that cannot convert to a number are also excluded and counted separately.

For finite values `x[1] ... x[n]`, the definitions are:

- mean: arithmetic mean, calculated with compensated summation after division by the maximum
  absolute finite value;
- median: empirical `p=0.5` quantile;
- variance: `sum((x[i] - mean)^2) / (n - ddof)`, with configurable `ddof` of 0 or 1;
- standard deviation: the non-negative square root of that variance estimator;
- quartiles: empirical `p=0.25` and `p=0.75` quantiles using index `h=(n-1)p`;
- IQR: Q3 minus Q1;
- skewness: bias-corrected Fisher-Pearson standardized moment. With central moments
  `m[k] = sum((x[i]-mean)^k)/n`, HaraLens reports
  `sqrt(n(n-1))/(n-2) * m[3]/m[2]^(3/2)` for `n >= 3`;
- kurtosis: bias-corrected Fisher/excess kurtosis, not Pearson kurtosis. If
  `g2=m[4]/m[2]^2-3`, HaraLens reports
  `(n-1)*((n+1)*g2+6)/((n-2)*(n-3))` for `n >= 4`.

The five quantile interpolation policies are explicit: `linear` interpolates between the two
bracketing values; `lower` chooses the lower value; `higher` chooses the higher value;
`midpoint` averages both; and `nearest` chooses the nearest indexed observation using the
underlying even-index tie convention. The default is `linear`.

With `ddof=1`, variance and standard deviation require at least two finite observations. With
`ddof=0`, one finite observation has zero variance and standard deviation. Skewness requires
three observations and kurtosis requires four. For a constant sample meeting those minimums,
both standardized moments are defined by the engine as `0.0`. A statistic that lacks enough
observations, has no finite input, is mathematically undefined, or exceeds finite IEEE-754
output range is `null`.

The implementation computes mean, dispersion, quantiles, IQR, skewness, and kurtosis on values
normalized by the maximum absolute finite magnitude, then reverses scaling where applicable.
This preserves finite results around `1e308` where direct summation or interpolation could
overflow. Minimum and maximum retain integer values where the input representation permits
it. Independent regression calculations use relative and absolute tolerances of `1e-12` to
allow normal binary floating-point rounding without accepting estimator changes.

No outlier boundary or outlier count is calculated in Phase 1D.

## Categorical and Boolean statistics

Categorical, Boolean, and non-numeric constant columns report a mode, bounded leading value
frequencies, remaining-value count, and Shannon entropy in bits. Counts use all non-null
rows. Percentages use the non-null count.

Category identity and category display are separate. Exact counting uses a full typed key:
Boolean, integer, float, date, datetime, and string have distinct type tags; strings use their
complete content; floats use their exact hexadecimal representation; dates/datetimes use full
ISO representations. Consequently `1` and `"1"`, `False` and `0`, and a date and equivalent
text remain distinct. `category_count` and the column cardinality fields use this typed
identity for categorical profiles.

Ordering is deterministic and does not use dictionary/hash iteration order: descending count,
then lexicographic canonical type tag, then the complete canonical identity representation.
The first item is the mode. A tie crossing the top-K boundary therefore selects the same
categories regardless of source order. Mixed scalar types are compared only through canonical
strings, so Python never compares unlike scalar objects directly.

`top_values_limit` bounds output size; `other_value_count` keeps the result arithmetically
complete. Display rendering happens only after counts and ordering are final. Long displayed
strings are truncated at the configured bound and carry `truncated=true`, their original
length, and a 64-character SHA-256 fingerprint of the full string. The fingerprint preserves
bounded deterministic distinguishability when two labels share the visible prefix. It is not
used as category identity, so digest collisions cannot merge or alter counts.

The engine does not identify rare or inconsistent categories and does not attach a quality
meaning to cardinality or entropy.

## Datetime statistics

Datetime columns report parsed, unparsed, and ambiguous non-null counts; timezone awareness;
earliest/latest ISO representations; and span in seconds.

The parser follows the deliberately narrow Phase 1C surface: Python dates/datetimes, ISO
calendar text, and full slash-formatted calendar dates. A slash value valid under more than
one date ordering is excluded from the range and counted as ambiguous. HaraLens never assumes
a locale. Aware values are normalized to UTC for ordering while retaining their instant.
Naive values remain naive. If aware and naive values are mixed, range fields are withheld
with a typed warning because comparing them would require an unstated timezone assumption.

There is no future-date judgment, calendar-frequency inference, or timezone inference in
Phase 1D.

## Text and identifier statistics

Free-text and identifier columns report minimum, maximum, average, and median rendered length,
plus empty-string and whitespace-only counts. They do not retain samples, modes, or raw values.
This makes useful shape information available without copying identifiers or free text into
the profile.

Empty columns have no specialized statistics. Unknown columns also remain limited to common
facts. Constant columns use numeric, datetime, or categorical statistics according to their
physical representation.

## Configuration and resource behavior

`ProfilingConfig` defaults are:

| Setting | Default | Meaning |
| --- | ---: | --- |
| `max_rows` | 100,000 | Maximum exact-profile row count |
| `max_columns` | 1,000 | Maximum exact-profile column count |
| `max_cells` | 10,000,000 | Maximum rows multiplied by columns |
| `top_values_limit` | 10 | Maximum serialized categorical frequencies |
| `max_value_display_length` | 200 | Maximum displayed category string length |
| `standard_deviation_ddof` | 1 | Sample standard deviation/variance policy |
| `quantile_interpolation` | `linear` | Quartile interpolation policy |

The first three limits also protect callers that bypass ingestion and supply a DataFrame
directly. Exceeding one fails explicitly with `RESOURCE_LIMIT_EXCEEDED`; data is never
silently truncated or sampled. Custom ingestion policies and profiling policies should be
configured consistently by their future composition root. Each maximum is inclusive: exactly
the configured row, column, or cell count is accepted, while one over is rejected. Cell count
uses Python integer multiplication, which has arbitrary precision and cannot wrap around.

## Determinism, failure handling, and privacy

The result contains no timestamps, durations, random samples, unordered sets, or machine-
specific object addresses. Exact frequencies use a stable tie-break. Profile warnings expose
safe codes and explanations without exception text.

Every profile model rejects non-finite computed floats. Serialization uses standards-compliant
JSON: undefined results are `null`, and bare `NaN`, `Infinity`, or `-Infinity` tokens cannot
enter the result. Source infinities appear only through their integer counts in numeric
statistics.

An unexpected specialized-statistic failure is isolated to that column. Its common facts
remain available, later columns continue, and `failed_column_count` records the event. The
service does not log cell values. Bounded categorical frequency output is the only profile
path that includes observed values; identifier and free-text values are never retained.

## Semantic-profile consistency boundary

Phase 1D verifies shape, ordered column names, physical dtypes, total/null counts, and exact
distinct counts before using a semantic result. These checks detect a wrong table in common
cases, but a same-shape substitution or row permutation can preserve every checked fact.

A value fingerprint is deliberately deferred. A schema-only digest adds no protection beyond
the existing checks, while a correct full-data digest requires canonical rules for types,
nulls, timezone values, ordering, and source bytes and adds another complete data pass. The
Phase 3 dataset-versioning/persistence layer should bind ingestion content hashes, semantic
results, and profiles to one `DatasetVersion`; Phase 4 service composition should enforce that
binding at API/workflow boundaries. Until then, callers must keep the table and semantic
result together as one immutable in-memory analysis input.

## Phase boundary

Phase 1D intentionally excludes:

- outlier, rarity, invalidity, inconsistency, severity, or health decisions;
- potential PII and target-candidate inference;
- quality checks, scoring, and remediation recommendations;
- correlations, hypothesis tests, visualizations, ML readiness, reports, API routes, UI,
  authentication, persistence, and AI.

Those capabilities require separate contracts and explicit authorization in later phases.
