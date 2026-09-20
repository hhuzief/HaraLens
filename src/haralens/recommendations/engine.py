"""Map quality facts to safe, deterministic actions."""

from __future__ import annotations

import hashlib

from haralens.quality.models import QualityFinding, QualityRunResult, Severity
from haralens.scoring.models import HealthScoreResult

from .models import (
    Recommendation,
    RecommendationAction,
    RecommendationPriority,
    RecommendationResult,
)

_ACTION = {
    "completeness_missingness": (
        RecommendationAction.REVIEW_CAPTURE,
        "Review missing-value capture",
        "Review whether missing values are expected or indicate a source capture issue.",
    ),
    "empty_column": (
        RecommendationAction.INVESTIGATE_SOURCE,
        "Investigate empty column",
        "Confirm whether this column is intentionally empty in the source system.",
    ),
    "duplicate_rows": (
        RecommendationAction.VERIFY_RECORDS,
        "Verify duplicate records",
        "Review duplicate records against the source process before taking any destructive action.",
    ),
    "identifier_uniqueness": (
        RecommendationAction.VERIFY_RECORDS,
        "Review identifier generation",
        "Investigate why identifier values repeat among non-null observations.",
    ),
    "identifier_missingness": (
        RecommendationAction.REVIEW_CAPTURE,
        "Review identifier capture",
        "Investigate missing identifier values before using this field for joins or tracking.",
    ),
    "nonfinite_numeric": (
        RecommendationAction.INVESTIGATE_SOURCE,
        "Resolve non-finite numerics",
        "Review the source and downstream handling of infinite numeric values.",
    ),
    "category_consistency": (
        RecommendationAction.STANDARDIZE_REPRESENTATION,
        "Review category representation",
        "Review category formatting rules and standardize representations only with domain "
        "validation.",
    ),
    "column_label_consistency": (
        RecommendationAction.STANDARDIZE_REPRESENTATION,
        "Review column labels",
        "Review surrounding whitespace in column labels before publishing a shared schema.",
    ),
    "constant_column": (
        RecommendationAction.ESTABLISH_DOMAIN_RULES,
        "Review constant feature",
        "Confirm whether the constant column is intentional before using it in analysis or "
        "modeling.",
    ),
    "high_cardinality": (
        RecommendationAction.ESTABLISH_DOMAIN_RULES,
        "Review categorical cardinality",
        "Confirm whether this categorical field is appropriate for the intended analysis.",
    ),
    "semantic_readiness": (
        RecommendationAction.REVIEW_SEMANTIC_TYPE,
        "Review semantic interpretation",
        "Confirm the column meaning and type before downstream analysis.",
    ),
}


class RecommendationEngine:
    def generate(
        self, quality_result: QualityRunResult, health_result: HealthScoreResult | None = None
    ) -> RecommendationResult:
        del health_result
        grouped: dict[
            tuple[str, str, str], list[tuple[QualityFinding, RecommendationAction, str, str]]
        ] = {}
        for execution in quality_result.executions:
            for finding in execution.findings:
                family_value = next(
                    (m.value for m in finding.methodology if m.name == "finding_family"), "unknown"
                )
                family = family_value if isinstance(family_value, str) else "unknown"
                action, title, message = _ACTION.get(
                    family,
                    (
                        RecommendationAction.INVESTIGATE_SOURCE,
                        "Investigate quality finding",
                        "Review the affected scope and source process.",
                    ),
                )
                target = (
                    finding.target.column_name or "" if finding.target.column_name else "dataset"
                )
                grouped.setdefault((family, target, finding.dimension.value), []).append(
                    (finding, action, title, message)
                )
        recommendations = []
        for _key, entries in grouped.items():
            findings = sorted(entries, key=lambda item: item[0].finding_id)
            first = findings[0][0]
            severity = max(
                (item[0].severity for item in findings),
                key=lambda item: [
                    Severity.LOW,
                    Severity.MEDIUM,
                    Severity.HIGH,
                    Severity.CRITICAL,
                ].index(item),
            )
            priority = {
                Severity.CRITICAL: RecommendationPriority.URGENT,
                Severity.HIGH: RecommendationPriority.HIGH,
                Severity.MEDIUM: RecommendationPriority.MEDIUM,
                Severity.LOW: RecommendationPriority.LOW,
            }[severity]
            digest = hashlib.sha256(
                "|".join(item[0].finding_id for item in findings).encode()
            ).hexdigest()[:16]
            recommendations.append(
                Recommendation(
                    recommendation_id=f"REC_{digest}",
                    priority=priority,
                    action=findings[0][1],
                    title=findings[0][2],
                    message=findings[0][3],
                    source_finding_ids=tuple(item[0].finding_id for item in findings),
                    dimension=first.dimension.value,
                    target_column=first.target.column_name,
                )
            )
        recommendations.sort(
            key=lambda item: (
                list(RecommendationPriority).index(item.priority),
                item.recommendation_id,
            )
        )
        return RecommendationResult(
            quality_run_reference=quality_result.metadata.run_reference,
            recommendations=tuple(recommendations),
        )
