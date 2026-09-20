"""Deterministic insight generation from structured engine outputs."""

from haralens.analytics import AnalyticsResult
from haralens.insights.identifiers import build_insight_id
from haralens.insights.models import Insight, InsightFamily, InsightResult
from haralens.quality import QualityRunResult
from haralens.readiness import AIReadinessResult


def generate_insights(
    quality: QualityRunResult,
    readiness: AIReadinessResult,
    analytics: AnalyticsResult,
    *,
    display_limit: int = 8,
) -> InsightResult:
    insights: list[Insight] = []
    if readiness.blockers:
        insights.append(
            Insight(
                id=build_insight_id("READINESS_BLOCKERS", "dataset"),
                family=InsightFamily.READINESS,
                importance=95,
                title="AI readiness has preparation blockers",
                message=f"{len(readiness.blockers)} readiness dimensions require preparation before downstream modeling.",
                supporting_metrics={"readiness_score": readiness.overall_score},
            )
        )
    finding_index = 0
    for execution in quality.executions:
        for finding in execution.findings:
            finding_index += 1
            insights.append(
                Insight(
                    id=build_insight_id(
                        "QUALITY",
                        finding.check_id,
                        finding.target.column_name or "dataset",
                        str(finding_index),
                    ),
                    family=InsightFamily.QUALITY,
                    importance=90 if finding.severity.value in {"critical", "high"} else 65,
                    title="Quality finding requires review",
                    message=finding.message,
                    supporting_metrics={},
                    affected_targets=(finding.target.column_name,)
                    if finding.target.column_name
                    else (),
                )
            )
    for numeric_item in analytics.numeric:
        if numeric_item.outlier_count:
            insights.append(
                Insight(
                    id=build_insight_id("OUTLIERS", numeric_item.column_name),
                    family=InsightFamily.OUTLIERS,
                    importance=60,
                    title="Potential numeric outliers detected",
                    message=f"{numeric_item.column_name} contains {numeric_item.outlier_count} potential IQR outliers; legitimate extremes remain possible.",
                    supporting_metrics={
                        "outlier_count": numeric_item.outlier_count,
                        "outlier_percentage": numeric_item.outlier_percentage,
                    },
                    affected_targets=(numeric_item.column_name,),
                )
            )
    for pair in analytics.correlations:
        if abs(pair.coefficient) >= analytics.strong_correlation_threshold:
            direction = "positive" if pair.coefficient > 0 else "negative"
            insights.append(
                Insight(
                    id=build_insight_id("CORRELATION", pair.left, pair.right),
                    family=InsightFamily.CORRELATION,
                    importance=55,
                    title="Strong linear association observed",
                    message=f"{pair.left} and {pair.right} show a strong {direction} linear association (r = {pair.coefficient:.2f}) in {pair.observation_count} observations. This does not imply causation.",
                    supporting_metrics={
                        "correlation": pair.coefficient,
                        "observations": pair.observation_count,
                    },
                    affected_targets=(pair.left, pair.right),
                )
            )
    for categorical_item in analytics.categorical:
        if categorical_item.high_cardinality:
            insights.append(
                Insight(
                    id=build_insight_id("CARDINALITY", categorical_item.column_name),
                    family=InsightFamily.CARDINALITY,
                    importance=58,
                    title="High categorical cardinality",
                    message=f"{categorical_item.column_name} has high cardinality and may need encoding review.",
                    supporting_metrics={"cardinality": categorical_item.cardinality},
                    affected_targets=(categorical_item.column_name,),
                )
            )
    insights.sort(key=lambda item: (-item.importance, item.id))
    return InsightResult(insights=tuple(insights), display_limit=display_limit)
