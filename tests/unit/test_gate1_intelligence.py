from __future__ import annotations

import json

import pandas as pd

from haralens.profiling import profile_dataset
from haralens.quality import (
    QualityCheckContext,
    QualityCheckRunner,
    QualityDimension,
    QualityFrameworkConfig,
    create_default_quality_registry,
)
from haralens.recommendations import RecommendationEngine
from haralens.scoring import HealthScorer, ScoreState, severity_prevalence_penalty
from haralens.semantic import infer_semantic_types


def _run(table: pd.DataFrame):
    semantic = infer_semantic_types(table)
    profile = profile_dataset(table, semantic)
    context = QualityCheckContext(table=table, semantic_profile=semantic, dataset_profile=profile)
    quality = QualityCheckRunner().run(
        context, create_default_quality_registry(), QualityFrameworkConfig()
    )
    health = HealthScorer().score(quality)
    recommendations = RecommendationEngine().generate(quality, health)
    return quality, health, recommendations


def test_default_catalogue_is_explicit_and_covers_all_dimensions() -> None:
    registry = create_default_quality_registry()
    assert len(registry) >= 10
    assert {entry.definition.dimension for entry in registry.entries} == set(QualityDimension)
    assert [entry.definition.check_id for entry in registry.entries] == sorted(
        entry.definition.check_id for entry in registry.entries
    )


def test_golden_chain_is_deterministic_and_privacy_safe() -> None:
    table = pd.DataFrame(
        {
            "id": ["secret-id", "secret-id", None],
            "value": [1.0, float("inf"), 2.0],
            "category": [" A ", "a", "B"],
            "constant": [1, 1, 1],
        }
    )
    first = _run(table)
    second = _run(table.copy())
    assert first[0].model_dump() == second[0].model_dump()
    assert first[1].model_dump() == second[1].model_dump()
    assert first[2].model_dump() == second[2].model_dump()
    encoded = json.dumps(first[2].model_dump(), allow_nan=False)
    assert "secret-id" not in encoded
    assert first[1].overall_score is not None
    assert 0 <= first[1].overall_score <= 100


def test_unevaluated_dimensions_are_not_perfect_scores() -> None:
    quality, health, _ = _run(pd.DataFrame({"x": [1, 2, 3]}))
    assert quality.summary.total_executions > 0
    assert all(
        item.state in (ScoreState.EVALUATED, ScoreState.NOT_EVALUATED) for item in health.dimensions
    )
    for item in health.dimensions:
        if item.state is ScoreState.NOT_EVALUATED:
            assert item.score is None


def test_scoring_is_monotone_for_more_missing_values() -> None:
    clean = _run(pd.DataFrame({"value": [1, 2, 3, 4]}))[1]
    degraded = _run(pd.DataFrame({"value": [1, None, None, None]}))[1]
    clean_dimension = next(
        item for item in clean.dimensions if item.dimension.value == "completeness"
    )
    degraded_dimension = next(
        item for item in degraded.dimensions if item.dimension.value == "completeness"
    )
    assert degraded_dimension.score <= clean_dimension.score


def test_severity_prevalence_penalty_table_is_monotone_and_structural() -> None:
    prevalences = (0.01, 0.10, 0.50, 1.0)
    severities = ("low", "medium", "high", "critical")
    from haralens.quality import Severity

    table = {
        severity: [
            severity_prevalence_penalty(Severity(severity), prevalence)
            for prevalence in prevalences
        ]
        for severity in severities
    }
    assert all(values == sorted(values) for values in table.values())
    for left, right in zip(severities, severities[1:], strict=False):
        assert all(a < b for a, b in zip(table[left], table[right], strict=True))
    assert severity_prevalence_penalty(Severity.MEDIUM, None) == table["medium"][-1]


def test_nonfinite_check_is_column_scoped_and_empty_columns_are_not_double_counted() -> None:
    table = pd.DataFrame({"number": [1.0, float("inf"), 3.0], "empty": [None, None, None]})
    quality, health, _ = _run(table)
    nonfinite = [
        item for item in quality.executions if item.check_id == "DQ_VALIDITY_NONFINITE_NUMERIC"
    ]
    assert all(item.scope.value == "column" for item in nonfinite)
    assert any(item.findings for item in nonfinite)
    empty_findings = [
        finding
        for item in quality.executions
        if item.check_id == "DQ_COMPLETENESS_EMPTY_COLUMN"
        for finding in item.findings
    ]
    missing_findings = [
        finding
        for item in quality.executions
        if item.check_id == "DQ_COMPLETENESS_COLUMN_MISSINGNESS"
        for finding in item.findings
        if finding.target.column_name == "empty"
    ]
    assert empty_findings
    assert not missing_findings
    assert health.overall_score is not None


def test_constant_policy_skips_all_null_identifier_and_one_row_columns() -> None:
    for table in (
        pd.DataFrame({"x": [None, None]}),
        pd.DataFrame({"id": ["a", "b"]}),
        pd.DataFrame({"x": [1]}),
    ):
        quality, _, _ = _run(table)
        constants = [
            finding
            for item in quality.executions
            if item.check_id == "DQ_READINESS_CONSTANT_COLUMN"
            for finding in item.findings
        ]
        assert not constants


def test_identifier_missingness_is_visible_twice_but_penalized_once() -> None:
    table = pd.DataFrame(
        {
            "identifier": [
                None,
                *[f"550e8400-e29b-41d4-a716-4466554400{i:02d}" for i in range(1, 20)],
            ]
        }
    )
    quality, health, _ = _run(table)
    source_findings = [
        finding
        for item in quality.executions
        if item.check_id
        in {"DQ_COMPLETENESS_COLUMN_MISSINGNESS", "DQ_INTEGRITY_IDENTIFIER_MISSINGNESS"}
        for finding in item.findings
    ]
    assert len(source_findings) == 2
    integrity = next(item for item in health.dimensions if item.dimension.value == "integrity")
    completeness = next(
        item for item in health.dimensions if item.dimension.value == "completeness"
    )
    linked = [
        item
        for item in [*integrity.penalties, *completeness.penalties]
        if item.penalty_group == "identifier_missingness"
    ]
    assert sum(item.applied for item in linked) == 1
    assert any(item.linked_to_finding_id for item in linked if not item.applied)
