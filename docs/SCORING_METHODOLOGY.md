# Proposed scoring methodology

**Design only. No scoring implementation or calibrated thresholds exist in Phase 0.**

Dimensions: Completeness, Uniqueness, Validity, Consistency, Integrity, and
Analytical Readiness. The overall score is not a probability of correctness or a
guarantee of model performance.

For eligible checks in dimension d, let p_i be a bounded penalty in [0, 1],
combining affected proportion and a documented severity multiplier. Let w_i be a
nonnegative importance weight. A proposed normalized formulation is:

```text
dimension_score_d = 100 * (1 - sum(w_i * p_i) / sum(w_i))
overall_score = sum(W_d * dimension_score_d) / sum(W_d)
```

Only evaluated, applicable checks/dimensions enter the denominators. Zero total
weight yields an unavailable score with a reason, never an automatic 100. Failed,
skipped or unsupported checks must be reported separately from passed checks.
Show evaluation coverage beside any score. Reject nonfinite inputs and negative
weights. Do not count overlapping evidence repeatedly without an explicit policy.

Before implementation, version and document severity mappings, dimension weights,
thresholds, overlap handling, and sample-derived estimates. Retain dataset version,
formula version, complete configuration, affected counts, denominators, evidence,
and contribution details. No arbitrary numeric weights are approved here.

Phase 1 tests must establish bounds, monotonicity, known examples, zero denominators,
missing dimensions, nonfinite inputs, reproducibility and sampling disclosures.
