"""Deterministic, bounded, explainable health scoring."""

from __future__ import annotations

from collections import defaultdict

from haralens.quality.models import QualityDimension, QualityOutcome, QualityRunResult, Severity

from .models import (
    DimensionHealthScore,
    HealthScoreResult,
    HealthScoringConfig,
    InterpretationBand,
    PenaltyContribution,
    ScoreState,
)

_BASE = {
    Severity.LOW: 0.20,
    Severity.MEDIUM: 0.40,
    Severity.HIGH: 0.55,
    Severity.CRITICAL: 0.80,
}


def severity_prevalence_penalty(severity: Severity, prevalence: float | None) -> float:
    """Return the bounded v0.1 penalty in points for one finding.

    ``None`` is the explicit structural policy and is treated as prevalence 1.0.
    """

    normalized = 1.0 if prevalence is None else max(0.0, min(1.0, prevalence))
    return min(100.0, _BASE[severity] * (0.25 + 0.75 * normalized) * 100)


class HealthScorer:
    """Scores only findings already produced by the quality runner.

    For each finding, penalty = base(severity) * (0.25 + 0.75 * prevalence).
    Structural findings without a denominator use prevalence 1.0. Findings in the same
    family and target are deduplicated by retaining the largest penalty.
    """

    def __init__(self, configuration: HealthScoringConfig | None = None) -> None:
        self.configuration = configuration or HealthScoringConfig()

    def score(self, result: QualityRunResult) -> HealthScoreResult:
        by_dim: dict[QualityDimension, list[PenaltyContribution]] = defaultdict(list)
        candidates: list[PenaltyContribution] = []
        for execution in result.executions:
            for finding in execution.findings:
                family_value = next(
                    (m.value for m in finding.methodology if m.name == "finding_family"),
                    "unknown",
                )
                family = family_value if isinstance(family_value, str) else "unknown"
                root_value = next(
                    (m.value for m in finding.methodology if m.name == "root_cause_group"),
                    family,
                )
                root_group = root_value if isinstance(root_value, str) else family
                population = finding.affected_population
                prevalence = (
                    1.0
                    if population is None or population.affected_percentage is None
                    else population.affected_percentage / 100
                )
                penalty = severity_prevalence_penalty(finding.severity, prevalence)
                contribution = PenaltyContribution(
                    finding_id=finding.finding_id,
                    check_id=finding.check_id,
                    dimension=finding.dimension,
                    severity=finding.severity,
                    finding_family=family,
                    penalty_group=root_group,
                    target_key=finding.target.model_dump_json(),
                    prevalence=prevalence,
                    penalty_points=penalty,
                    explanation=(
                        f"{finding.severity.value} severity at {prevalence * 100:.2f}% prevalence."
                    ),
                )
                candidates.append(contribution)
        primaries: dict[tuple[str, str], PenaltyContribution] = {}
        for candidate in candidates:
            key = (candidate.penalty_group, candidate.target_key)
            current = primaries.get(key)
            if current is None or (candidate.penalty_points, candidate.finding_id) > (
                current.penalty_points,
                current.finding_id,
            ):
                primaries[key] = candidate
        for candidate in candidates:
            key = (candidate.penalty_group, candidate.target_key)
            primary = primaries[key]
            applied = candidate.finding_id == primary.finding_id
            by_dim[candidate.dimension].append(
                candidate.model_copy(
                    update={
                        "applied": applied,
                        "linked_to_finding_id": None if applied else primary.finding_id,
                    }
                )
            )
        dimensions: list[DimensionHealthScore] = []
        evaluated_weights = {
            d: self.configuration.weights[d] for d in QualityDimension if _executed(result, d)
        }
        weight_sum = sum(evaluated_weights.values())
        for dimension in QualityDimension:
            executions = sum(
                1
                for item in result.executions
                if item.dimension is dimension and item.outcome is not QualityOutcome.NOT_EVALUATED
            )
            if not executions:
                dimensions.append(
                    DimensionHealthScore(
                        dimension=dimension, state=ScoreState.NOT_EVALUATED, executed_check_count=0
                    )
                )
                continue
            penalties = tuple(
                sorted(by_dim.get(dimension, []), key=lambda p: (p.check_id, p.finding_id))
            )
            score = max(
                0.0,
                100.0 - min(100.0, sum(p.penalty_points for p in penalties if p.applied)),
            )
            dimensions.append(
                DimensionHealthScore(
                    dimension=dimension,
                    state=ScoreState.EVALUATED,
                    score=score,
                    executed_check_count=executions,
                    effective_weight=evaluated_weights[dimension] / weight_sum
                    if weight_sum
                    else None,
                    penalties=penalties,
                )
            )
        evaluated = [
            d for d in dimensions if d.state is ScoreState.EVALUATED and d.score is not None
        ]
        overall = (
            sum((d.score or 0.0) * (d.effective_weight or 0.0) for d in evaluated)
            if evaluated
            else None
        )
        return HealthScoreResult(
            quality_run_reference=result.metadata.run_reference,
            configuration_fingerprint=self.configuration.fingerprint,
            dimensions=tuple(dimensions),
            overall_score=overall,
            overall_state=ScoreState.EVALUATED if overall is not None else ScoreState.NOT_EVALUATED,
            interpretation=_band(overall),
        )


def _executed(result: QualityRunResult, dimension: QualityDimension) -> bool:
    return any(
        item.dimension is dimension and item.outcome is not QualityOutcome.NOT_EVALUATED
        for item in result.executions
    )


def _band(score: float | None) -> InterpretationBand | None:
    if score is None:
        return None
    if score >= 90:
        return InterpretationBand.EXCELLENT
    if score >= 75:
        return InterpretationBand.GOOD
    if score >= 60:
        return InterpretationBand.NEEDS_ATTENTION
    if score >= 40:
        return InterpretationBand.POOR
    return InterpretationBand.CRITICAL
