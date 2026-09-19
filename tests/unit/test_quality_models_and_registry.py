"""Unit tests for Phase 1E models, configuration, and explicit registry."""

from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from haralens.quality import (
    QUALITY_DIMENSION_TAXONOMY_VERSION,
    QUALITY_FRAMEWORK_VERSION,
    AffectedPopulation,
    CheckApplicability,
    CheckEvaluation,
    CheckExecutionResult,
    CheckExecutionStatus,
    CheckPrerequisite,
    CheckScope,
    ConditionOperator,
    DuplicateCheckIdError,
    EvidenceSource,
    FindingDraft,
    MethodologyMetadata,
    PopulationBasis,
    QualityCheckConfiguration,
    QualityCheckDefinition,
    QualityCheckRegistry,
    QualityCondition,
    QualityConfigParameter,
    QualityDimension,
    QualityEvidence,
    QualityFrameworkConfig,
    QualityOutcome,
    QualityResourceLimits,
    QualityTarget,
    Severity,
    UnknownCheckIdError,
)
from haralens.semantic.models import SemanticType


def definition(
    check_id: str = "DQ_TEST_ALPHA",
    *,
    dimension: QualityDimension = QualityDimension.COMPLETENESS,
    scope: CheckScope = CheckScope.DATASET,
    default_enabled: bool = True,
) -> QualityCheckDefinition:
    return QualityCheckDefinition(
        check_id=check_id,
        check_version="1.0.0",
        display_name="Test check",
        dimension=dimension,
        scope=scope,
        description="A test-only framework check.",
        default_enabled=default_enabled,
    )


@dataclass
class NoopCheck:
    definition: QualityCheckDefinition

    def validate_configuration(self, configuration: object) -> None:
        del configuration

    def select_targets(self, context: object) -> tuple[QualityTarget, ...]:
        del context
        return (QualityTarget(scope=CheckScope.DATASET),)

    def assess_applicability(
        self, context: object, target: QualityTarget, configuration: object
    ) -> CheckApplicability:
        del context, target, configuration
        return CheckApplicability(applicable=True)

    def evaluate(
        self, context: object, target: QualityTarget, configuration: object, resources: object
    ) -> CheckEvaluation:
        del context, target, configuration, resources
        return CheckEvaluation(outcome=QualityOutcome.PASS)


def test_taxonomy_and_versions_are_stable() -> None:
    assert QUALITY_FRAMEWORK_VERSION == "1.0.0"
    assert QUALITY_DIMENSION_TAXONOMY_VERSION == "1.0.0"
    assert [item.value for item in QualityDimension] == [
        "completeness",
        "uniqueness",
        "validity",
        "consistency",
        "integrity",
        "analytical_readiness",
    ]
    assert [item.value for item in CheckScope] == ["dataset", "column", "multi_column"]


def test_definition_normalizes_metadata_and_rejects_invalid_dataset_semantics() -> None:
    item = QualityCheckDefinition(
        check_id="DQ_TEST_COLUMN",
        check_version="2.3.4",
        display_name="Column test",
        dimension=QualityDimension.VALIDITY,
        scope=CheckScope.COLUMN,
        description="Test definition.",
        supported_semantic_types=(SemanticType.NUMERIC_DISCRETE, SemanticType.BOOLEAN),
        tags=("zeta", "alpha"),
    )
    assert item.tags == ("alpha", "zeta")
    assert item.supported_semantic_types == (
        SemanticType.BOOLEAN,
        SemanticType.NUMERIC_DISCRETE,
    )
    with pytest.raises(ValidationError, match="dataset checks"):
        definition(scope=CheckScope.DATASET).model_copy(
            update={"supported_semantic_types": (SemanticType.BOOLEAN,)}
        ).model_validate(
            {
                **definition().model_dump(),
                "supported_semantic_types": (SemanticType.BOOLEAN,),
            }
        )


@pytest.mark.parametrize(
    "updates",
    [
        {"supported_semantic_types": (SemanticType.BOOLEAN, SemanticType.BOOLEAN)},
        {"tags": ("duplicate", "duplicate")},
        {"prerequisites": (CheckPrerequisite.TABLE, CheckPrerequisite.TABLE)},
    ],
)
def test_definition_rejects_duplicate_metadata(updates: dict[str, object]) -> None:
    payload = {
        **definition(scope=CheckScope.COLUMN).model_dump(),
        **updates,
    }
    with pytest.raises(ValidationError, match="must be unique"):
        QualityCheckDefinition.model_validate(payload)


@pytest.mark.parametrize(
    "target",
    [
        QualityTarget(scope=CheckScope.DATASET),
        QualityTarget(scope=CheckScope.COLUMN, column_name="a", column_position=0),
        QualityTarget(
            scope=CheckScope.MULTI_COLUMN,
            column_names=("a", "b"),
            column_positions=(0, 1),
        ),
    ],
)
def test_target_scope_shapes_round_trip(target: QualityTarget) -> None:
    assert QualityTarget.model_validate_json(target.model_dump_json()) == target


def test_invalid_target_shapes_are_rejected() -> None:
    with pytest.raises(ValidationError):
        QualityTarget(scope=CheckScope.COLUMN)
    with pytest.raises(ValidationError):
        QualityTarget(
            scope=CheckScope.MULTI_COLUMN,
            column_names=("a",),
            column_positions=(0,),
        )
    with pytest.raises(ValidationError, match="dataset targets"):
        QualityTarget(scope=CheckScope.DATASET, column_name="a", column_position=0)


@pytest.mark.parametrize(
    ("affected_count", "population_count", "expected_percentage"),
    [(0, 0, None), (0, 1, 0.0), (1, 1, 100.0), (25, 100, 25.0)],
)
def test_affected_population_records_reconstructable_denominator(
    affected_count: int,
    population_count: int,
    expected_percentage: float | None,
) -> None:
    population = AffectedPopulation.from_counts(
        affected_count,
        population_count,
        PopulationBasis.NON_NULL_ROWS,
    )
    assert population.affected_percentage == expected_percentage
    assert json.loads(population.model_dump_json())["affected_percentage"] == expected_percentage


def test_affected_population_rejects_invalid_counts_and_percentage_semantics() -> None:
    with pytest.raises(ValidationError, match="less than or equal|affected_count"):
        AffectedPopulation(
            affected_count=2,
            population_count=1,
            affected_percentage=100.0,
            basis=PopulationBasis.TOTAL_ROWS,
        )
    with pytest.raises(ValidationError, match="undefined percentage"):
        AffectedPopulation(
            affected_count=0,
            population_count=0,
            affected_percentage=0.0,
            basis=PopulationBasis.TOTAL_ROWS,
        )
    with pytest.raises(ValidationError, match="require an affected percentage"):
        AffectedPopulation(
            affected_count=0,
            population_count=1,
            affected_percentage=None,
            basis=PopulationBasis.TOTAL_ROWS,
        )
    with pytest.raises(ValidationError, match="match the supplied counts"):
        AffectedPopulation(
            affected_count=1,
            population_count=4,
            affected_percentage=20.0,
            basis=PopulationBasis.TOTAL_ROWS,
        )
    with pytest.raises(ValidationError, match="only valid for custom"):
        AffectedPopulation.from_counts(
            1,
            4,
            PopulationBasis.TOTAL_ROWS,
            basis_description="Not allowed for this basis.",
        )
    with pytest.raises(ValidationError, match="description"):
        AffectedPopulation.from_counts(1, 1, PopulationBasis.CUSTOM)


def test_structured_condition_and_evidence_are_scalar_and_json_safe() -> None:
    condition = QualityCondition(
        metric_name="missing_percentage",
        operator=ConditionOperator.LESS_THAN_OR_EQUAL,
        expected=10.0,
    )
    evidence = QualityEvidence(
        metric_name="missing_percentage",
        source=EvidenceSource.COLUMN_PROFILE,
        observed=25.0,
        expected=10.0,
        operator=ConditionOperator.LESS_THAN_OR_EQUAL,
        profile_field="missing_percentage",
    )
    payload = json.loads(condition.model_dump_json())
    assert payload["expected"] == 10.0
    assert json.loads(evidence.model_dump_json())["observed"] == 25.0
    custom = QualityCondition(
        metric_name="custom_metric",
        operator=ConditionOperator.CUSTOM,
        description="A bounded custom condition.",
    )
    assert custom.expected is None
    with pytest.raises(ValidationError):
        QualityEvidence(metric_name="value", source=EvidenceSource.TABLE, observed=float("nan"))
    with pytest.raises(ValidationError, match="custom conditions"):
        QualityCondition(metric_name="custom_metric", operator=ConditionOperator.CUSTOM)
    with pytest.raises(ValidationError, match="expected scalar"):
        QualityCondition(
            metric_name="row_count",
            operator=ConditionOperator.EQUAL,
        )


def test_evaluation_and_execution_invariants() -> None:
    draft = FindingDraft(
        severity=Severity.LOW,
        message="A bounded test finding.",
        evidence=(
            QualityEvidence(
                metric_name="row_count", source=EvidenceSource.DATASET_PROFILE, observed=0
            ),
        ),
    )
    with pytest.raises(ValidationError, match="passed evaluation"):
        CheckEvaluation(outcome=QualityOutcome.PASS, findings=(draft,))
    with pytest.raises(ValidationError, match="requires at least one"):
        CheckEvaluation(outcome=QualityOutcome.FAIL)
    with pytest.raises(ValidationError, match="pass or fail"):
        CheckExecutionResult(
            check_id="DQ_TEST_ALPHA",
            check_version="1.0.0",
            dimension=QualityDimension.COMPLETENESS,
            scope=CheckScope.DATASET,
            target=QualityTarget(scope=CheckScope.DATASET),
            execution_status=CheckExecutionStatus.EXECUTED,
            outcome=QualityOutcome.NOT_EVALUATED,
            configuration_fingerprint="0" * 64,
        )


def test_informational_severity_is_reserved_outside_failed_findings() -> None:
    with pytest.raises(ValidationError, match="informational severity"):
        FindingDraft(
            severity=Severity.INFORMATIONAL,
            message="An invalid informational failure.",
            evidence=(
                QualityEvidence(
                    metric_name="row_count",
                    source=EvidenceSource.DATASET_PROFILE,
                    observed=0,
                ),
            ),
        )


def test_finding_draft_rejects_duplicate_methodology_and_warning_codes() -> None:
    evidence = (
        QualityEvidence(
            metric_name="row_count",
            source=EvidenceSource.DATASET_PROFILE,
            observed=1,
        ),
    )
    with pytest.raises(ValidationError, match="methodology names"):
        FindingDraft(
            severity=Severity.LOW,
            message="Duplicate methodology.",
            evidence=evidence,
            methodology=(
                MethodologyMetadata(name="method", value="a"),
                MethodologyMetadata(name="method", value="b"),
            ),
        )
    with pytest.raises(ValidationError, match="warning codes"):
        FindingDraft(
            severity=Severity.LOW,
            message="Duplicate warnings.",
            evidence=evidence,
            warning_codes=("TEST_WARNING", "TEST_WARNING"),
        )


def test_evaluation_and_applicability_reject_contradictory_states() -> None:
    with pytest.raises(ValidationError, match="pass or fail"):
        CheckEvaluation(outcome=QualityOutcome.NOT_EVALUATED)
    with pytest.raises(ValidationError, match="applicable checks"):
        CheckApplicability(
            applicable=True,
            reason_code="NOT_ALLOWED",
            message="An applicable target cannot carry this reason.",
        )
    with pytest.raises(ValidationError, match="require a code and message"):
        CheckApplicability(applicable=False)


def test_strict_configuration_and_canonical_fingerprint() -> None:
    left = QualityFrameworkConfig(
        enabled_check_ids=("DQ_TEST_BETA", "DQ_TEST_ALPHA"),
        disabled_check_ids=("DQ_TEST_DELTA", "DQ_TEST_GAMMA"),
        included_dimensions=(QualityDimension.VALIDITY, QualityDimension.COMPLETENESS),
        check_configurations=(
            QualityCheckConfiguration(
                check_id="DQ_TEST_ALPHA",
                parameters=(
                    QualityConfigParameter(name="zeta", value=2),
                    QualityConfigParameter(name="alpha", value=1),
                ),
            ),
        ),
    )
    right = QualityFrameworkConfig(
        enabled_check_ids=("DQ_TEST_ALPHA", "DQ_TEST_BETA"),
        disabled_check_ids=("DQ_TEST_GAMMA", "DQ_TEST_DELTA"),
        included_dimensions=(QualityDimension.COMPLETENESS, QualityDimension.VALIDITY),
        check_configurations=(
            QualityCheckConfiguration(
                check_id="DQ_TEST_ALPHA",
                parameters=(
                    QualityConfigParameter(name="alpha", value=1),
                    QualityConfigParameter(name="zeta", value=2),
                ),
            ),
        ),
    )
    assert left == right
    assert left.fingerprint == right.fingerprint
    assert len(left.fingerprint) == 64
    assert (
        left.fingerprint
        != QualityFrameworkConfig(
            enabled_check_ids=("DQ_TEST_ALPHA", "DQ_TEST_BETA"),
            disabled_check_ids=("DQ_TEST_GAMMA", "DQ_TEST_DELTA"),
            included_dimensions=(QualityDimension.COMPLETENESS, QualityDimension.VALIDITY),
            fail_fast_internal_errors=True,
            check_configurations=right.check_configurations,
        ).fingerprint
    )
    assert left.check_configurations[0].fingerprint == right.check_configurations[0].fingerprint
    with pytest.raises(ValidationError):
        QualityFrameworkConfig(enabled_check_ids=("invalid",))
    with pytest.raises(ValidationError, match="both explicitly"):
        QualityFrameworkConfig(
            enabled_check_ids=("DQ_TEST_ALPHA",),
            disabled_check_ids=("DQ_TEST_ALPHA",),
        )
    with pytest.raises(ValidationError):
        QualityFrameworkConfig.model_validate({"unknown": True})
    with pytest.raises(ValidationError):
        QualityResourceLimits(max_rows_per_check=0)
    with pytest.raises(ValidationError, match="parameter names"):
        QualityCheckConfiguration(
            check_id="DQ_TEST_ALPHA",
            parameters=(
                QualityConfigParameter(name="threshold", value=1),
                QualityConfigParameter(name="threshold", value=2),
            ),
        )
    with pytest.raises(ValidationError, match="cannot contain duplicates"):
        QualityFrameworkConfig(enabled_check_ids=("DQ_TEST_ALPHA", "DQ_TEST_ALPHA"))
    with pytest.raises(ValidationError, match="included dimensions"):
        QualityFrameworkConfig(
            included_dimensions=(QualityDimension.VALIDITY, QualityDimension.VALIDITY)
        )
    duplicate_configuration = QualityCheckConfiguration(check_id="DQ_TEST_ALPHA")
    with pytest.raises(ValidationError, match="one configuration"):
        QualityFrameworkConfig(
            check_configurations=(duplicate_configuration, duplicate_configuration)
        )


def test_registry_empty_single_lookup_filters_and_order() -> None:
    empty = QualityCheckRegistry()
    assert len(empty) == 0
    assert empty.definitions() == ()
    alpha = NoopCheck(definition("DQ_TEST_ALPHA"))
    beta = NoopCheck(
        definition(
            "DQ_TEST_BETA",
            dimension=QualityDimension.VALIDITY,
            scope=CheckScope.COLUMN,
        )
    )
    registry = QualityCheckRegistry((beta, alpha))
    assert [item.check_id for item in registry.definitions()] == [
        "DQ_TEST_ALPHA",
        "DQ_TEST_BETA",
    ]
    assert registry.get("DQ_TEST_ALPHA").check is alpha
    assert registry.definitions(dimension=QualityDimension.VALIDITY) == (beta.definition,)
    assert registry.definitions(scope=CheckScope.COLUMN) == (beta.definition,)
    assert registry.entries == tuple(registry.entries)
    assert registry.fingerprint == QualityCheckRegistry((alpha, beta)).fingerprint
    with pytest.raises(UnknownCheckIdError):
        registry.get("DQ_TEST_MISSING")


def test_registry_rejects_duplicate_stable_ids() -> None:
    item = NoopCheck(definition())
    with pytest.raises(DuplicateCheckIdError):
        QualityCheckRegistry((item, NoopCheck(definition())))
