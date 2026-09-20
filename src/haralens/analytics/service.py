"""Bounded numerical and categorical analytics built on the ingested frame."""

from __future__ import annotations

import math

import pandas as pd

from haralens.analytics.models import (
    AnalyticsResult,
    CategoricalAnalytics,
    CorrelationPair,
    NumericAnalytics,
)
from haralens.profiling import CategoricalStatistics, DatasetProfile, NumericStatistics
from haralens.semantic import DatasetSemanticProfile

CORRELATION_COLUMN_LIMIT = 40
STRONG_CORRELATION_THRESHOLD = 0.8


def analyze_frame(
    frame: pd.DataFrame,
    profile: DatasetProfile,
    semantic: DatasetSemanticProfile,
    *,
    correlation_column_limit: int = CORRELATION_COLUMN_LIMIT,
    strong_correlation_threshold: float = STRONG_CORRELATION_THRESHOLD,
) -> AnalyticsResult:
    """Calculate exact bounded diagnostics without changing the source frame."""

    numeric: list[NumericAnalytics] = []
    categorical: list[CategoricalAnalytics] = []
    eligible_numeric = [
        c.column_name
        for c in semantic.columns
        if c.effective_type.value in {"numeric_continuous", "numeric_discrete"}
    ]
    for column in profile.columns:
        stats = column.statistics
        if isinstance(stats, NumericStatistics):
            values = pd.to_numeric(frame[column.column_name], errors="coerce")
            finite = values[values.apply(math.isfinite)]
            q1 = stats.first_quartile
            q3 = stats.third_quartile
            iqr = stats.interquartile_range
            lower = q1 - 1.5 * iqr if q1 is not None and iqr is not None else None
            upper = q3 + 1.5 * iqr if q3 is not None and iqr is not None else None
            outliers = (
                int(((finite < lower) | (finite > upper)).sum())
                if lower is not None and upper is not None
                else 0
            )
            skew = stats.skewness
            interpretation = (
                "undefined"
                if skew is None
                else "approximately symmetric"
                if abs(skew) < 0.5
                else "moderately skewed"
                if abs(skew) < 1.0
                else "strongly skewed"
            )
            numeric.append(
                NumericAnalytics(
                    column_name=column.column_name,
                    finite_count=len(finite),
                    outlier_count=outliers,
                    outlier_percentage=100 * outliers / len(finite) if len(finite) else 0.0,
                    lower_bound=lower,
                    upper_bound=upper,
                    skewness_interpretation=interpretation,
                )
            )
        if isinstance(stats, CategoricalStatistics):
            top = stats.mode
            categorical.append(
                CategoricalAnalytics(
                    column_name=column.column_name,
                    cardinality=stats.category_count,
                    top_category_share=top.percentage if top else None,
                    entropy_bits=stats.entropy_bits,
                    high_cardinality=(
                        stats.category_count > max(20, int(column.non_null_count * 0.5))
                    ),
                )
            )
    bounded_numeric = eligible_numeric[:correlation_column_limit]
    correlations: list[CorrelationPair] = []
    if len(bounded_numeric) > 1:
        numeric_frame = frame[bounded_numeric].apply(pd.to_numeric, errors="coerce")
        for index, left in enumerate(bounded_numeric):
            for right in bounded_numeric[index + 1 :]:
                pair = (
                    numeric_frame[[left, right]]
                    .replace([float("inf"), float("-inf")], pd.NA)
                    .dropna()
                )
                if len(pair) < 2 or pair[left].nunique() < 2 or pair[right].nunique() < 2:
                    continue
                coefficient = float(pair[left].corr(pair[right], method="pearson"))
                if math.isfinite(coefficient):
                    correlations.append(
                        CorrelationPair(
                            left=left,
                            right=right,
                            coefficient=coefficient,
                            observation_count=len(pair),
                        )
                    )
    return AnalyticsResult(
        numeric=tuple(numeric),
        categorical=tuple(categorical),
        correlations=tuple(correlations),
        correlation_column_limit=correlation_column_limit,
        strong_correlation_threshold=strong_correlation_threshold,
    )
