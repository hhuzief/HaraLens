"""Conservative, deterministic technical readiness assessment."""

from __future__ import annotations

import pandas as pd

from haralens.analytics import AnalyticsResult
from haralens.profiling import DatasetProfile
from haralens.readiness.models import (
    AIReadinessResult,
    ReadinessBand,
    ReadinessDimension,
    TargetAnalysis,
)
from haralens.semantic import DatasetSemanticProfile

WEIGHTS = {
    "data_sufficiency": 0.15,
    "data_completeness": 0.20,
    "feature_usability": 0.20,
    "type_readiness": 0.15,
    "cardinality_risk": 0.10,
    "distribution_risk": 0.10,
    "data_integrity": 0.10,
}


def assess_readiness(
    frame: pd.DataFrame,
    semantic: DatasetSemanticProfile,
    profile: DatasetProfile,
    analytics: AnalyticsResult,
    *,
    target_name: str | None = None,
) -> AIReadinessResult:
    rows = len(frame)
    columns = list(profile.columns)
    usable = [
        c
        for c in semantic.columns
        if c.effective_type.value
        in {"numeric_continuous", "numeric_discrete", "categorical", "boolean", "datetime"}
        and c.effective_type.value
        not in {"identifier", "free_text", "constant", "empty", "unknown"}
    ]
    missing_pct = profile.summary.missing_percentage
    completeness = max(0.0, 100.0 - missing_pct)
    sufficiency = min(100.0, 40.0 + min(rows, 1000) / 10.0)
    feature_score = 100.0 * len(usable) / len(columns) if columns else 0.0
    unsupported = sum(
        c.effective_type.value in {"free_text", "unknown", "empty"} for c in semantic.columns
    )
    type_score = 100.0 * (1 - unsupported / len(columns)) if columns else 0.0
    high_card = sum(item.high_cardinality for item in analytics.categorical)
    cardinality_score = (
        100.0 * (1 - high_card / len(analytics.categorical)) if analytics.categorical else 100.0
    )
    outlier_columns = sum(item.outlier_count > 0 for item in analytics.numeric)
    distribution_score = (
        100.0 * (1 - outlier_columns / len(analytics.numeric)) if analytics.numeric else 100.0
    )
    duplicate_percentage = profile.summary.duplicate_row_percentage or 0.0
    integrity_score = (
        100.0
        if profile.summary.duplicate_row_count in (None, 0)
        else max(0.0, 100.0 - duplicate_percentage)
    )
    values = {
        "data_sufficiency": (
            sufficiency,
            f"{rows} rows and {len(usable)} potentially usable predictors measured",
        ),
        "data_completeness": (completeness, f"{missing_pct:.2f}% of cells are missing"),
        "feature_usability": (
            feature_score,
            f"{len(usable)} of {len(columns)} columns are candidate features",
        ),
        "type_readiness": (
            type_score,
            f"{unsupported} columns have unsupported or ambiguous semantic types",
        ),
        "cardinality_risk": (
            cardinality_score,
            f"{high_card} categorical columns exceed the high-cardinality rule",
        ),
        "distribution_risk": (
            distribution_score,
            f"{outlier_columns} numeric columns contain potential IQR outliers",
        ),
        "data_integrity": (
            integrity_score,
            "duplicate-row prevalence is included as a neutral integrity signal",
        ),
    }
    dimensions = tuple(
        ReadinessDimension(
            name=name,
            score=score,
            weight=WEIGHTS[name],
            measurement=measurement,
            effect=f"Weighted contribution: {score * WEIGHTS[name]:.2f} points",
        )
        for name, (score, measurement) in values.items()
    )
    score = round(sum(item.score * item.weight for item in dimensions), 3)
    band = (
        ReadinessBand.HIGHLY_READY
        if score >= 90
        else ReadinessBand.READY
        if score >= 75
        else ReadinessBand.PREPARATION_RECOMMENDED
        if score >= 60
        else ReadinessBand.SIGNIFICANT_PREPARATION
        if score >= 40
        else ReadinessBand.NOT_READY
    )
    blockers = tuple(item.name for item in dimensions if item.score < 40)
    warnings = tuple(item.measurement for item in dimensions if item.score < 75)
    strengths = tuple(item.name for item in dimensions if item.score >= 90)
    target = _target_analysis(frame, target_name) if target_name else None
    if target and target.constant:
        blockers += ("selected target is constant",)
    return AIReadinessResult(
        overall_score=score,
        band=band,
        dimensions=dimensions,
        blockers=blockers,
        warnings=warnings,
        strengths=strengths,
        contributing_factors=tuple(item.measurement for item in dimensions),
        target=target,
    )


def _target_analysis(frame: pd.DataFrame, target_name: str) -> TargetAnalysis:
    if target_name not in frame.columns:
        raise ValueError(f"Unknown target column: {target_name}")
    series = frame[target_name]
    non_null = series.dropna()
    cardinality = int(non_null.nunique(dropna=True))
    identifier_like = len(non_null) > 0 and cardinality / len(non_null) >= 0.95
    if pd.api.types.is_numeric_dtype(series):
        kind = "regression_candidate" if cardinality > 10 else "classification_candidate"
    else:
        kind = "classification_candidate"
    counts = non_null.value_counts(normalize=True)
    minority_ratio = float(counts.min()) if len(counts) > 1 else None
    observations: list[str] = []
    if series.isna().any():
        observations.append(f"{int(series.isna().sum())} target observations are missing")
    if cardinality == 1:
        observations.append("The selected target is constant")
    if identifier_like:
        observations.append("The selected target is identifier-like")
    if minority_ratio is not None and minority_ratio < 0.1:
        observations.append("The minority class is below the documented 10% advisory threshold")
    return TargetAnalysis(
        target_name=target_name,
        target_kind=kind,
        missing_count=int(series.isna().sum()),
        cardinality=cardinality,
        minority_ratio=minority_ratio,
        constant=cardinality <= 1,
        identifier_like=identifier_like,
        observations=tuple(observations),
    )
