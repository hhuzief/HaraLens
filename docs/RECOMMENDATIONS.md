# HaraLens v0.1 recommendations

`RecommendationEngine` maps finding families to safe, non-destructive investigation actions.
Recommendations retain every source finding ID and group related findings by family, target,
and dimension. Priority is deterministic: critical is urgent, high is high, medium is medium,
and low is low. Messages may mention bounded column names under the existing contract but never
emit cell values, category examples, identifiers, or free text. Recommendations do not delete,
impute, mutate, or rewrite data.
