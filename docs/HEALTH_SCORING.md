# HaraLens v0.1 health scoring

Scoring is a separate consumer of `QualityRunResult`; it never rescans the table or invents
quality facts. The default dimension weights are completeness .20, uniqueness .15, validity
.20, consistency .15, integrity .20, and analytical readiness .10. Weights are renormalized
over dimensions with at least one evaluated execution. A dimension with no evaluated checks is
`NOT_EVALUATED`, has a null score, and contributes no weight.

For each finding, let `b` be the calibrated severity base (low .20, medium .40, high .55,
critical .80). These bases reserve a meaningful minimum deduction for a structural defect while
leaving prevalence to control the remainder; they are HaraLens methodology defaults, not universal
scientific constants.
and `p` be affected prevalence in [0, 1]. Structural findings without a denominator use
`p = 1`. The penalty is `100 * b * (0.25 + 0.75p)`. Findings with the same dimension, family,
and target are deduplicated by retaining the largest penalty. Dimension score is
`max(0, 100 - min(100, sum(unique penalties)))`. Overall score is the weighted sum of evaluated
dimension scores. All calculations are finite, bounded, deterministic, and versioned as 1.0.0.

Interpretation bands are product methodology labels: excellent 90–100, good 75–<90,
needs_attention 60–<75, poor 40–<60, and critical 0–<40.
