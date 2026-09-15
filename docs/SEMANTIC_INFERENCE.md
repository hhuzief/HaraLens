# Semantic type inference

## Scope and guarantee

HaraLens Phase 1C separates a column's physical pandas dtype from its likely analytical
meaning. The engine is a reusable Python package and has no dependency on FastAPI,
Streamlit, persistence, profiling, quality scoring, machine learning, or an LLM.

> Semantic type inference is heuristic and explainable, not infallible.

Given the same table, configuration, and inference version, the engine returns the same
ordered result. It does not mutate the input table and does not log or retain raw cell
values. Results contain safe counts, ratios, evidence codes, warnings, and type candidates.

## Public API

```python
from haralens.semantic import SemanticInferenceConfig, infer_semantic_types

profile = infer_semantic_types(dataframe, SemanticInferenceConfig())
```

`SemanticInferenceService.infer()` accepts either a pandas `DataFrame` or an
`IngestionResult`. `SemanticInferenceEngine.infer_column()` provides the lower-level column
operation. The service preserves column order and uses physical position to ensure duplicate
DataFrame labels still receive separate results. Phase 1 ingestion already guarantees unique
string labels.

## Stable taxonomy

| Semantic type | Meaning |
| --- | --- |
| `empty` | Every row is null, including a zero-row column |
| `constant` | Exactly one distinct non-null value |
| `boolean` | Native boolean or a deliberately recognized binary representation |
| `datetime` | Native datetime/date values or sufficiently parseable date-like text |
| `identifier` | UUIDs or high-uniqueness values supported by identifier-name/structure evidence |
| `numeric_discrete` | Integer-like numeric values with bounded or low cardinality |
| `numeric_continuous` | Fractional numeric values, high-cardinality numeric values, or measurements |
| `categorical` | Native pandas categories or repeated text with bounded cardinality |
| `free_text` | Long descriptive text supported by length and structure/uniqueness evidence |
| `unknown` | Evidence is insufficient, mixed, or unsafe to compare |

The taxonomy and engine currently use inference version `1.0.0`. Currency, percentage, and
ordinal candidates are intentionally absent because Phase 1C cannot assign them reliably
without stronger domain context.

## Inference precedence

The engine applies this explicit order:

1. all-null columns become `empty`;
2. one-valued non-null columns become `constant`;
3. native booleans and supported textual boolean pairs become `boolean`;
4. native pandas datetimes and Python date/datetime objects become `datetime`;
5. canonical UUID strings become `identifier`;
6. supported date-like text meeting the parse threshold becomes `datetime` unless a stronger
   identifier-name conflict exists;
7. numeric `0/1` with a flag-name hint becomes `boolean`;
8. candidate/high-uniqueness values with weighted token-aware identifier evidence may become
   `identifier`;
9. physical numeric columns become `numeric_discrete` or `numeric_continuous`;
10. native pandas categorical columns become `categorical`;
11. long descriptive strings become `free_text`;
12. repeated bounded-cardinality strings become `categorical`;
13. unsupported, mixed, or weak evidence becomes `unknown`.

This order prevents null and constant structure from being hidden by dtype, prevents unique
dates from becoming identifiers through uniqueness alone, and lets descriptive text win over
low cardinality when long passages repeat.

## Evidence and warnings

Every result contains at least one structured `InferenceEvidence`. Codes are stable enum
values rather than prose-only explanations. Major groups include:

- structure: `ALL_NULL`, `CONSTANT_VALUE`, `NULL_VALUES_PRESENT`;
- physical representation: `NATIVE_BOOLEAN_DTYPE`, `NATIVE_DATETIME_DTYPE`,
  `NATIVE_NUMERIC_DTYPE`, `NATIVE_CATEGORICAL_DTYPE`;
- boolean: `BOOLEAN_VALUE_SET`, `BOOLEAN_NAME_HINT`, `BINARY_NUMERIC_SET`, `BINARY_TEXT_SET`;
- identifier: `UUID_PATTERN`, `NAME_HINT_IDENTIFIER`, `HIGH_UNIQUENESS`,
  `IDENTIFIER_CANDIDATE_UNIQUENESS`, `MONOTONIC_INTEGER_SEQUENCE`,
  `STRUCTURED_CODE_PATTERN`;
- datetime: `PYTHON_DATE_VALUES`, `DATE_LIKE_PATTERN`, `DATE_PARSE_RATE`,
  `AMBIGUOUS_DATE_FORMAT`;
- numeric/text: `NUMERIC_INTEGER_ONLY`, `NUMERIC_FRACTIONAL_VALUES`,
  `LOW_CARDINALITY`, `HIGH_CARDINALITY`, `NAME_HINT_CATEGORICAL`, `LONG_TEXT`,
  `NAME_HINT_FREE_TEXT`, `HIGH_TEXT_UNIQUENESS`, `TEXT_WHITESPACE`;
- operation: `DETERMINISTIC_SAMPLE`, `MIXED_VALUE_TYPES`,
  `UNSUPPORTED_PHYSICAL_DTYPE`, `INFERENCE_ERROR`.

Evidence may carry only a safe observed count/ratio and its threshold. It never carries a
sample value. Warnings identify ambiguity, partial parsing, small observation counts,
unsupported values, and isolated column failures. Alternatives are ordered typed candidates
with their supporting evidence codes.

## Confidence method

Confidence is the discrete enum `high`, `medium`, or `low`; the engine does not manufacture
probabilistic precision.

- `high` means direct physical/structural evidence or multiple strong rules agree.
- `medium` means a documented heuristic wins while another meaning remains plausible.
- `low` means evidence is ambiguous, unsupported, or insufficient.

When the non-null count is below `minimum_confident_non_null`, high confidence is reduced to
medium and medium to low. Empty and constant results remain high because their evidence is
exact. Ambiguous slash dates are always low confidence because no locale ordering is chosen.

## Default configuration

`SemanticInferenceConfig` is immutable, strict, and rejects unknown fields or coercion.

| Setting | Default | Use |
| --- | ---: | --- |
| `categorical_max_unique_count` | 20 | Maximum distinct count supporting repeated categories |
| `categorical_max_unique_ratio` | 0.05 | Maximum repeated-label ratio supporting categories |
| `identifier_min_unique_ratio` | 0.98 | Strong identifier uniqueness |
| `identifier_candidate_min_unique_ratio` | 0.80 | Repeated-identifier candidate floor |
| `identifier_min_non_null` | 4 | Minimum observations for name-assisted identifiers |
| `numeric_discrete_max_unique_count` | 20 | Integer-like discrete cardinality boundary |
| `numeric_discrete_max_unique_ratio` | 0.05 | Integer-like discrete ratio boundary |
| `free_text_min_average_length` | 40.0 | Average inspected text length boundary |
| `free_text_min_unique_ratio` | 0.50 | Uniqueness evidence for free text |
| `free_text_min_whitespace_ratio` | 0.50 | Whitespace/structure evidence boundary |
| `datetime_min_parse_ratio` | 0.90 | Required parse success among inspected non-null values |
| `minimum_confident_non_null` | 10 | Small-sample confidence boundary |
| `max_inspection_values` | 10,000 | Maximum values inspected by content rules |

All ratios divide by the non-null count. `nullable` records whether the observed column
contains at least one null. `null_count`, `non_null_count`, `unique_count`, and `unique_ratio`
are computed over the full bounded column. Content rules use all non-null values up to the
inspection limit; above it they use evenly spaced physical positions including both ends.
DataFrame index labels do not affect selection. The result records `sample_count` and
`sampled`. There is no random state.

## Important heuristics

### Boolean

Native booleans are direct evidence. Text is trimmed and case-folded only for detection; the
source remains unchanged. `true/false` is strong Boolean evidence; `yes/no` and `y/n` are
Boolean with medium confidence. Both textual and numeric `0/1` require a flag-like name token
such as `is`, `has`, `flag`, `active`, or `enabled`. Without that hint, numeric values remain
`numeric_discrete` and text values remain `categorical`; both expose `boolean` as an
alternative with an ambiguity warning. Other two-label sets such as `Male/Female` remain
categorical.

### Identifier

The evidence hierarchy is:

1. Canonical UUID text is direct structural evidence. Repeated UUIDs retain identifier
   meaning with reduced confidence and a duplicate warning.
2. Strong tokens `id` and `uuid` require at least the candidate uniqueness ratio. High
   confidence additionally requires strong uniqueness plus monotonic or code structure.
3. Contextual tokens `account`, `code`, `key`, `number`, `no`, and `reference` require an
   identifier entity such as customer, invoice, order, product, phone, transaction, or
   account. Generic `reference` also requires value structure. Measurement and categorical
   context blocks these weaker hints.

CamelCase and separators are tokenized, so `CustomerID` matches but `identity_score` does
not. Ratios from 0.80 through the strong 0.98 boundary preserve plausible repeated
identifiers with reduced confidence; lower ratios do not infer identifiers. Monotonic integer
or alphanumeric code structure strengthens existing name/context evidence but never forces
an identifier independently. Names and uniqueness also never decide identifier type alone.

### Datetime

Native datetime dtypes and Python date objects are recognized directly. String parsing is
limited to anchored ISO calendar text and slash-formatted full calendar dates. Pure integers,
compact values such as `20240101`, ordinal codes such as `2024-001`, partial year-month values
such as `2024-01`, embedded date segments in product/version codes, and Unix timestamps are
not parsed. Slash values valid under both month/day and day/month orderings return `datetime`
with low confidence, an ambiguity warning, and no chosen locale. Timezone suffixes may be
recognized syntactically, but the engine never infers timezone meaning beyond the supplied
offset.

### Numeric

Numeric dtype alone establishes only the numeric family. Fractional values and configured
measurement-name hints support `numeric_continuous`. For other integer-like data, the
absolute distinct-count threshold is evaluated first. Above that boundary, the ratio
threshold supports `numeric_discrete` only when the name also has categorical context.
Otherwise the result is continuous. A small ratio alone therefore cannot turn a 500- or
2,000-valued measurement into discrete data.

### Categorical and free text

Native pandas categories are categorical. Other text must repeat. The absolute distinct-count
threshold is evaluated first; above it, the ratio threshold requires categorical name
context such as category, class, label, region, segment, status, or type. High-cardinality
generic labels remain unknown even when their ratio is small. Free text requires average
length plus uniqueness, whitespace/punctuation structure, or a descriptive name hint. The
implementation uses basic string features only, with no NLP or language model.

## Confidence policy

High confidence is reserved for exact empty/constant structure, native Boolean/datetime/
categorical dtypes, fully inspected explicit `true/false` or ISO date syntax, unique canonical
UUIDs, exact binary values with flag-name support, physical fractional numerics, and strong
unique identifier name-plus-structure combinations. Content classifications derived from a
sample cannot become high confidence. Inferred categories and free text are capped at medium;
repeated identifiers, `yes/no`, partial date parsing, and other conflicts are medium or low.

## Failure isolation and privacy

Unhashable or unsafe-to-compare values produce `unknown`, optional metrics, and a typed
warning. An unexpected exception in one column is isolated by the dataset service; later
columns still receive results. Neither exception details nor raw values enter the result.
No semantic inference path logs values. This phase does not attempt PII detection.

## User override extension

`ColumnSemanticInference.semantic_type` is the engine's inferred type.
`user_confirmed_type` is an optional future override slot, and the `effective_type` property
returns the override when present. Phase 1C does not add persistence, APIs, or UI for setting
overrides.

## Known limitations

- Heuristics cannot establish business meaning or ground truth.
- Ambiguous dates remain ambiguous; there is no locale configuration in this phase.
- Uniqueness counts scan the complete bounded column and can still be material work near the
  Phase 1B row/column limits.
- Sampling can miss rare content patterns, and its use is explicit in each result.
- Email, PII, currency, percentage, ordinal, Unix-time, and domain-schema inference are out
  of scope.
- Complex numbers and arbitrary nested objects degrade safely to `unknown`; Phase 1B
  ingestion rejects nested Parquet structures before this service.
