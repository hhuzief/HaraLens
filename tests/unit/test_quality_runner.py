"""End-to-end tests for the Phase 1E runner using test-only checks."""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import dataclass

import pandas as pd
import pytest
from pydantic import ValidationError

import haralens.quality.runner as quality_runner_module
from haralens.profiling import profile_dataset
from haralens.quality import (
    AffectedPopulation,
    CheckApplicability,
    CheckDataUnsupportedError,
    CheckEvaluation,
    CheckExecutionStatus,
    CheckPrerequisite,
    CheckPrerequisiteError,
    CheckResourceLimitError,
    CheckScope,
    ConditionOperator,
    EvidenceSource,
    FindingDraft,
    PopulationBasis,
    QualityCheckConfiguration,
    QualityCheckContext,
    QualityCheckDefinition,
    QualityCheckRegistry,
    QualityCheckRunner,
    QualityConfigParameter,
    QualityConfigurationError,
    QualityContextError,
    QualityDimension,
    QualityEvidence,
    QualityFrameworkConfig,
    QualityOutcome,
    QualityResourceError,
    QualityResourceLimits,
    QualityTarget,
    Severity,
    UnexpectedCheckError,
)
from haralens.semantic import infer_semantic_types
from haralens.semantic.models import SemanticType

ErrorFactory = Callable[[], Exception]


@dataclass
class TestCheck:
    """Minimal configurable check fixture; never included in product registration."""

    __test__ = False

    definition: QualityCheckDefinition
    outcome: QualityOutcome = QualityOutcome.PASS
    severity: Severity = Severity.MEDIUM
    inapplicable_positions: tuple[int, ...] = ()
    expected_error: ErrorFactory | None = None
    unexpected_message: str | None = None
    explicit_targets: tuple[QualityTarget, ...] | None = None
    reject_configuration: bool = False
    mutate_table: bool = False
    expected_table: pd.DataFrame | None = None
    evidence_observed: int = 1

    def validate_configuration(self, configuration: QualityCheckConfiguration | None) -> None:
        if self.reject_configuration or (
            configuration is not None and configuration.parameter("threshold") == -1
        ):
            raise ValueError("test configuration rejected")

    def select_targets(self, context: QualityCheckContext) -> tuple[QualityTarget, ...]:
        if self.explicit_targets is not None:
            return self.explicit_targets
        if self.definition.scope is CheckScope.DATASET:
            return (context.dataset_target(),)
        if self.definition.scope is CheckScope.COLUMN:
            return context.column_targets()
        columns = context.dataset_profile.columns
        if len(columns) < 2:
            return ()
        return (
            QualityTarget(
                scope=CheckScope.MULTI_COLUMN,
                column_names=(columns[0].column_name, columns[1].column_name),
                column_positions=(0, 1),
            ),
        )

    def assess_applicability(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
    ) -> CheckApplicability:
        del configuration
        if target.column_position in self.inapplicable_positions:
            return CheckApplicability(
                applicable=False,
                reason_code="SEMANTIC_TYPE_UNSUPPORTED",
                message="The target semantic type is unsupported.",
            )
        if self.definition.supported_semantic_types and target.column_position is not None:
            semantic_type = context.column_semantic(target.column_position).effective_type
            if semantic_type not in self.definition.supported_semantic_types:
                return CheckApplicability(
                    applicable=False,
                    reason_code="SEMANTIC_TYPE_UNSUPPORTED",
                    message="The target semantic type is unsupported.",
                )
        return CheckApplicability(applicable=True)

    def evaluate(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
        resources: QualityResourceLimits,
    ) -> CheckEvaluation:
        del configuration, resources
        if self.mutate_table:
            context.table.iloc[0, 0] = 999
            context.table["injected_by_test"] = "mutation"
            context.table.loc[len(context.table)] = [0] * len(context.table.columns)
        if self.expected_table is not None:
            pd.testing.assert_frame_equal(context.table, self.expected_table)
        if self.expected_error is not None:
            raise self.expected_error()
        if self.unexpected_message is not None:
            raise RuntimeError(self.unexpected_message)
        if self.outcome is QualityOutcome.PASS:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        affected = AffectedPopulation.from_counts(
            1,
            len(context.table),
            PopulationBasis.TOTAL_ROWS,
        )
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                FindingDraft(
                    severity=self.severity,
                    message="A test-only condition was observed.",
                    affected_population=affected,
                    condition=None,
                    evidence=(
                        QualityEvidence(
                            metric_name="affected_count",
                            source=EvidenceSource.TABLE,
                            observed=self.evidence_observed,
                            expected=0,
                            operator=ConditionOperator.EQUAL,
                        ),
                    ),
                    warning_codes=("TEST_ONLY",),
                ),
            ),
        )


@pytest.fixture
def quality_context() -> QualityCheckContext:
    table = pd.DataFrame(
        {
            "amount": [1.0, None, 3.5],
            "category": ["alpha", "alpha", "beta"],
            "active": [True, False, True],
        }
    )
    semantic = infer_semantic_types(table)
    profile = profile_dataset(table, semantic)
    return QualityCheckContext(
        table=table,
        semantic_profile=semantic,
        dataset_profile=profile,
    )


def make_definition(
    check_id: str,
    *,
    dimension: QualityDimension = QualityDimension.COMPLETENESS,
    scope: CheckScope = CheckScope.DATASET,
    default_enabled: bool = True,
    check_version: str = "1.0.0",
    supported_semantic_types: tuple[SemanticType, ...] = (),
    prerequisites: tuple[CheckPrerequisite, ...] = (
        CheckPrerequisite.TABLE,
        CheckPrerequisite.SEMANTIC_PROFILE,
        CheckPrerequisite.DATASET_PROFILE,
    ),
) -> QualityCheckDefinition:
    return QualityCheckDefinition(
        check_id=check_id,
        check_version=check_version,
        display_name=f"Test {check_id}",
        dimension=dimension,
        scope=scope,
        description="A test-only quality-check fixture.",
        default_enabled=default_enabled,
        supported_semantic_types=supported_semantic_types,
        prerequisites=prerequisites,
    )


def run(
    quality_context: QualityCheckContext,
    *checks: TestCheck,
    config: QualityFrameworkConfig | None = None,
):
    return QualityCheckRunner().run(
        quality_context,
        QualityCheckRegistry(checks),
        config,
    )


def test_empty_registry_produces_complete_neutral_summary(
    quality_context: QualityCheckContext,
) -> None:
    result = run(quality_context)
    assert result.executions == ()
    assert result.summary.total_executions == 0
    assert len(result.dimensions) == len(QualityDimension)
    assert all(item.total_executions == 0 for item in result.dimensions)
    assert result.metadata.registered_check_count == 0


def test_dataset_check_executes_exactly_once(quality_context: QualityCheckContext) -> None:
    result = run(
        quality_context,
        TestCheck(make_definition("DQ_TEST_DATASET")),
    )
    assert len(result.executions) == 1
    execution = result.executions[0]
    assert execution.target == QualityTarget(scope=CheckScope.DATASET)
    assert execution.execution_status is CheckExecutionStatus.EXECUTED
    assert execution.outcome is QualityOutcome.PASS


def test_column_targets_follow_physical_source_order(
    quality_context: QualityCheckContext,
) -> None:
    result = run(
        quality_context,
        TestCheck(
            make_definition("DQ_TEST_COLUMNS", scope=CheckScope.COLUMN),
            explicit_targets=tuple(reversed(quality_context.column_targets())),
        ),
    )
    assert [item.target.column_position for item in result.executions if item.target] == [0, 1, 2]
    assert [item.target.column_name for item in result.executions if item.target] == [
        "amount",
        "category",
        "active",
    ]


def test_mixed_scopes_and_multi_column_extension(quality_context: QualityCheckContext) -> None:
    result = run(
        quality_context,
        TestCheck(make_definition("DQ_TEST_DATASET")),
        TestCheck(make_definition("DQ_TEST_COLUMN", scope=CheckScope.COLUMN)),
        TestCheck(make_definition("DQ_TEST_MULTI", scope=CheckScope.MULTI_COLUMN)),
    )
    assert [item.scope for item in result.executions] == [
        CheckScope.COLUMN,
        CheckScope.COLUMN,
        CheckScope.COLUMN,
        CheckScope.DATASET,
        CheckScope.MULTI_COLUMN,
    ]
    multi = result.executions[-1].target
    assert multi is not None
    assert multi.column_positions == (0, 1)


def test_applicability_is_distinct_from_pass_and_skip(
    quality_context: QualityCheckContext,
) -> None:
    result = run(
        quality_context,
        TestCheck(
            make_definition(
                "DQ_TEST_NUMERIC",
                scope=CheckScope.COLUMN,
                supported_semantic_types=(
                    SemanticType.NUMERIC_CONTINUOUS,
                    SemanticType.NUMERIC_DISCRETE,
                ),
            )
        ),
    )
    statuses = [item.execution_status for item in result.executions]
    assert statuses == [
        CheckExecutionStatus.EXECUTED,
        CheckExecutionStatus.NOT_APPLICABLE,
        CheckExecutionStatus.NOT_APPLICABLE,
    ]
    assert result.summary.passed == 1
    assert result.summary.not_applicable == 2


def test_disabled_default_disabled_and_dimension_filter_are_skipped(
    quality_context: QualityCheckContext,
) -> None:
    explicit = TestCheck(make_definition("DQ_TEST_EXPLICIT"))
    default_off = TestCheck(make_definition("DQ_TEST_DEFAULT_OFF", default_enabled=False))
    filtered = TestCheck(make_definition("DQ_TEST_FILTERED", dimension=QualityDimension.VALIDITY))
    result = run(
        quality_context,
        explicit,
        default_off,
        filtered,
        config=QualityFrameworkConfig(
            disabled_check_ids=("DQ_TEST_EXPLICIT",),
            enabled_check_ids=("DQ_TEST_DEFAULT_OFF",),
            included_dimensions=(QualityDimension.COMPLETENESS,),
        ),
    )
    by_id = {item.check_id: item for item in result.executions}
    assert by_id["DQ_TEST_EXPLICIT"].status_code == "CHECK_DISABLED"
    assert by_id["DQ_TEST_DEFAULT_OFF"].execution_status is CheckExecutionStatus.EXECUTED
    assert by_id["DQ_TEST_FILTERED"].status_code == "DIMENSION_FILTERED"
    assert result.summary.skipped == 2


def test_missing_ingestion_prerequisite_is_skipped(
    quality_context: QualityCheckContext,
) -> None:
    check = TestCheck(
        make_definition(
            "DQ_TEST_INGESTION",
            prerequisites=(CheckPrerequisite.INGESTION_METADATA,),
        )
    )
    execution = run(quality_context, check).executions[0]
    assert execution.execution_status is CheckExecutionStatus.SKIPPED
    assert execution.status_code == "PREREQUISITE_UNAVAILABLE"


@pytest.mark.parametrize(
    ("factory", "status"),
    [
        (
            lambda: CheckPrerequisiteError("TEST_PREREQUISITE", "Prerequisite unavailable."),
            CheckExecutionStatus.SKIPPED,
        ),
        (
            lambda: CheckResourceLimitError("TEST_RESOURCE_LIMIT", "Resource limit reached."),
            CheckExecutionStatus.SKIPPED,
        ),
        (
            lambda: CheckDataUnsupportedError("TEST_UNSUPPORTED", "Data shape unsupported."),
            CheckExecutionStatus.NOT_APPLICABLE,
        ),
    ],
)
def test_expected_check_limitations_are_isolated(
    quality_context: QualityCheckContext,
    factory: ErrorFactory,
    status: CheckExecutionStatus,
) -> None:
    limited = TestCheck(make_definition("DQ_TEST_LIMITED"), expected_error=factory)
    healthy = TestCheck(make_definition("DQ_TEST_Z_HEALTHY"))
    result = run(quality_context, limited, healthy)
    assert result.executions[0].execution_status is status
    assert result.executions[0].outcome is QualityOutcome.NOT_EVALUATED
    assert result.executions[0].findings == ()
    assert result.executions[1].outcome is QualityOutcome.PASS


def test_unexpected_failure_is_error_and_never_quality_failure(
    quality_context: QualityCheckContext, caplog: pytest.LogCaptureFixture
) -> None:
    raw_value = "customer-secret-9981"
    broken = TestCheck(
        make_definition("DQ_TEST_BROKEN"),
        unexpected_message=f"bug exposed {raw_value}",
    )
    result = run(quality_context, broken)
    execution = result.executions[0]
    assert execution.execution_status is CheckExecutionStatus.ERROR
    assert execution.outcome is QualityOutcome.NOT_EVALUATED
    assert execution.findings == ()
    assert raw_value not in execution.message
    assert raw_value not in caplog.text
    assert "bug exposed" not in caplog.text


def test_fail_fast_raises_safely_redacted_error(
    quality_context: QualityCheckContext,
) -> None:
    raw_value = "private-record-value"
    broken = TestCheck(make_definition("DQ_TEST_BROKEN"), unexpected_message=raw_value)
    with pytest.raises(UnexpectedCheckError) as raised:
        run(
            quality_context,
            broken,
            config=QualityFrameworkConfig(fail_fast_internal_errors=True),
        )
    assert raw_value not in str(raised.value)


def test_failure_creates_deterministic_structured_finding(
    quality_context: QualityCheckContext,
) -> None:
    check = TestCheck(
        make_definition("DQ_TEST_FAILURE", dimension=QualityDimension.ANALYTICAL_READINESS),
        outcome=QualityOutcome.FAIL,
        severity=Severity.LOW,
    )
    result = run(quality_context, check)
    execution = result.executions[0]
    finding = execution.findings[0]
    assert execution.outcome is QualityOutcome.FAIL
    assert finding.severity is Severity.LOW
    assert finding.affected_population is not None
    assert finding.affected_population.population_count == 3
    assert finding.evidence[0].observed == 1
    assert finding.finding_id == run(quality_context, check).executions[0].findings[0].finding_id


def test_configuration_is_validated_and_unknown_ids_are_rejected(
    quality_context: QualityCheckContext,
) -> None:
    check = TestCheck(make_definition("DQ_TEST_CONFIG"))
    with pytest.raises(QualityConfigurationError, match="unknown"):
        run(
            quality_context,
            check,
            config=QualityFrameworkConfig(enabled_check_ids=("DQ_TEST_UNKNOWN",)),
        )
    invalid = QualityCheckConfiguration(
        check_id="DQ_TEST_CONFIG",
        parameters=(QualityConfigParameter(name="threshold", value=-1),),
    )
    with pytest.raises(QualityConfigurationError, match="validation failed"):
        run(
            quality_context,
            check,
            config=QualityFrameworkConfig(check_configurations=(invalid,)),
        )


def test_context_consistency_accepts_matching_artifacts(
    quality_context: QualityCheckContext,
) -> None:
    assert quality_context.column_profile(0) == quality_context.dataset_profile.columns[0]
    assert quality_context.column(0).equals(quality_context.table.iloc[:, 0])
    run(quality_context, TestCheck(make_definition("DQ_TEST_MATCH")))


def test_context_rejects_shape_order_and_stale_artifacts(
    quality_context: QualityCheckContext,
) -> None:
    shape = QualityCheckContext(
        table=quality_context.table.iloc[:, :2],
        semantic_profile=quality_context.semantic_profile,
        dataset_profile=quality_context.dataset_profile,
    )
    with pytest.raises(QualityContextError, match="shapes"):
        run(shape)

    order = QualityCheckContext(
        table=quality_context.table[["category", "amount", "active"]],
        semantic_profile=quality_context.semantic_profile,
        dataset_profile=quality_context.dataset_profile,
    )
    with pytest.raises(QualityContextError, match="column"):
        run(order)

    semantic_column = quality_context.semantic_profile.columns[0]
    stale_semantic = quality_context.semantic_profile.model_copy(
        update={
            "columns": (
                semantic_column.model_copy(
                    update={"unique_count": (semantic_column.unique_count or 0) + 1}
                ),
                *quality_context.semantic_profile.columns[1:],
            )
        }
    )
    with pytest.raises(QualityContextError, match="stale"):
        run(
            QualityCheckContext(
                table=quality_context.table,
                semantic_profile=stale_semantic,
                dataset_profile=quality_context.dataset_profile,
            )
        )

    stale_profile = quality_context.dataset_profile.model_copy(
        update={
            "summary": quality_context.dataset_profile.summary.model_copy(
                update={
                    "missing_cell_count": (
                        quality_context.dataset_profile.summary.missing_cell_count + 1
                    )
                }
            )
        }
    )
    with pytest.raises(QualityContextError, match="stale"):
        run(
            QualityCheckContext(
                table=quality_context.table,
                semantic_profile=quality_context.semantic_profile,
                dataset_profile=stale_profile,
            )
        )


def test_each_check_receives_an_isolated_copy_on_write_table(
    quality_context: QualityCheckContext,
) -> None:
    before_table = quality_context.table.copy(deep=True)
    before_semantic = quality_context.semantic_profile.model_dump_json()
    before_profile = quality_context.dataset_profile.model_dump_json()
    mutating_check = TestCheck(make_definition("DQ_TEST_A_MUTATION"), mutate_table=True)
    observing_check = TestCheck(
        make_definition("DQ_TEST_B_OBSERVER"),
        expected_table=before_table,
    )
    registry = QualityCheckRegistry((observing_check, mutating_check))
    config = QualityFrameworkConfig()
    before_registry = registry.fingerprint
    before_config = config.model_dump_json()
    result = QualityCheckRunner().run(quality_context, registry, config)
    assert [item.outcome for item in result.executions] == [
        QualityOutcome.PASS,
        QualityOutcome.PASS,
    ]
    pd.testing.assert_frame_equal(quality_context.table, before_table)
    assert quality_context.semantic_profile.model_dump_json() == before_semantic
    assert quality_context.dataset_profile.model_dump_json() == before_profile
    assert registry.fingerprint == before_registry
    assert config.model_dump_json() == before_config


def test_resource_boundaries_are_enforced(quality_context: QualityCheckContext) -> None:
    first = TestCheck(make_definition("DQ_TEST_FIRST"))
    second = TestCheck(make_definition("DQ_TEST_SECOND"))
    with pytest.raises(QualityResourceError, match="registered-check"):
        run(
            quality_context,
            first,
            second,
            config=QualityFrameworkConfig(resources=QualityResourceLimits(max_registered_checks=1)),
        )

    disabled_checks = (
        TestCheck(make_definition("DQ_TEST_DISABLED_A", default_enabled=False)),
        TestCheck(make_definition("DQ_TEST_DISABLED_B", default_enabled=False)),
    )
    with pytest.raises(QualityResourceError, match="execution budget"):
        run(
            quality_context,
            *disabled_checks,
            config=QualityFrameworkConfig(resources=QualityResourceLimits(max_total_executions=1)),
        )
    columns = TestCheck(make_definition("DQ_TEST_COLUMNS", scope=CheckScope.COLUMN))
    result = run(
        quality_context,
        columns,
        config=QualityFrameworkConfig(resources=QualityResourceLimits(max_targets_per_check=2)),
    )
    assert result.executions[0].status_code == "TARGET_LIMIT_EXCEEDED"
    with pytest.raises(QualityResourceError, match="execution budget"):
        run(
            quality_context,
            columns,
            config=QualityFrameworkConfig(resources=QualityResourceLimits(max_total_executions=2)),
        )


def test_invalid_or_duplicate_targets_become_internal_errors(
    quality_context: QualityCheckContext,
) -> None:
    wrong = TestCheck(
        make_definition("DQ_TEST_WRONG", scope=CheckScope.COLUMN),
        explicit_targets=(QualityTarget(scope=CheckScope.DATASET),),
    )
    duplicate_target = quality_context.column_targets()[0]
    duplicate = TestCheck(
        make_definition("DQ_TEST_DUPLICATE", scope=CheckScope.COLUMN),
        explicit_targets=(duplicate_target, duplicate_target),
    )
    results = run(quality_context, wrong, duplicate)
    assert all(item.execution_status is CheckExecutionStatus.ERROR for item in results.executions)

    invalid_collection = TestCheck(
        make_definition("DQ_TEST_INVALID_COLLECTION", scope=CheckScope.COLUMN),
        explicit_targets=[],  # type: ignore[arg-type] - intentionally violates the Protocol
    )
    invalid_result = run(quality_context, invalid_collection)
    assert invalid_result.executions[0].status_code == "INVALID_CHECK_TARGETS"


def test_empty_out_of_range_and_mismatched_targets_are_handled(
    quality_context: QualityCheckContext,
) -> None:
    empty = TestCheck(
        make_definition("DQ_TEST_EMPTY_TARGETS", scope=CheckScope.COLUMN),
        explicit_targets=(),
    )
    out_of_range = TestCheck(
        make_definition("DQ_TEST_OUT_OF_RANGE", scope=CheckScope.COLUMN),
        explicit_targets=(
            QualityTarget(scope=CheckScope.COLUMN, column_name="missing", column_position=99),
        ),
    )
    mismatched = TestCheck(
        make_definition("DQ_TEST_TARGET_NAME", scope=CheckScope.COLUMN),
        explicit_targets=(
            QualityTarget(scope=CheckScope.COLUMN, column_name="wrong", column_position=0),
        ),
    )
    result = run(quality_context, empty, out_of_range, mismatched)
    by_id = {item.check_id: item for item in result.executions}
    assert by_id["DQ_TEST_EMPTY_TARGETS"].execution_status is CheckExecutionStatus.NOT_APPLICABLE
    assert by_id["DQ_TEST_EMPTY_TARGETS"].status_code == "NO_TARGETS"
    assert by_id["DQ_TEST_OUT_OF_RANGE"].execution_status is CheckExecutionStatus.ERROR
    assert by_id["DQ_TEST_TARGET_NAME"].execution_status is CheckExecutionStatus.ERROR


def test_invalid_target_fails_fast_with_safe_framework_error(
    quality_context: QualityCheckContext,
) -> None:
    wrong = TestCheck(
        make_definition("DQ_TEST_WRONG_FAST", scope=CheckScope.COLUMN),
        explicit_targets=(QualityTarget(scope=CheckScope.DATASET),),
    )
    with pytest.raises(UnexpectedCheckError, match="wrong scope"):
        run(
            quality_context,
            wrong,
            config=QualityFrameworkConfig(fail_fast_internal_errors=True),
        )


def test_result_is_reproducible_and_strict_json_round_trips(
    quality_context: QualityCheckContext,
) -> None:
    checks = (
        TestCheck(make_definition("DQ_TEST_PASS")),
        TestCheck(
            make_definition("DQ_TEST_FAIL", dimension=QualityDimension.VALIDITY),
            outcome=QualityOutcome.FAIL,
        ),
        TestCheck(
            make_definition("DQ_TEST_NA", scope=CheckScope.COLUMN),
            inapplicable_positions=(0, 1, 2),
        ),
    )
    first = run(quality_context, *checks)
    second = run(quality_context, *checks)
    assert first == second
    encoded = first.model_dump_json()
    assert "NaN" not in encoded
    assert "Infinity" not in encoded
    assert json.loads(encoded)["metadata"]["run_reference"] == first.metadata.run_reference
    assert type(first).model_validate_json(encoded) == first


def test_golden_framework_result_covers_all_neutral_states(
    quality_context: QualityCheckContext,
) -> None:
    checks = (
        TestCheck(make_definition("DQ_TEST_A_PASS")),
        TestCheck(
            make_definition("DQ_TEST_B_FAIL", dimension=QualityDimension.UNIQUENESS),
            outcome=QualityOutcome.FAIL,
            severity=Severity.HIGH,
        ),
        TestCheck(
            make_definition("DQ_TEST_C_NA", scope=CheckScope.COLUMN),
            inapplicable_positions=(0, 1, 2),
        ),
        TestCheck(make_definition("DQ_TEST_D_DISABLED", default_enabled=False)),
    )
    result = run(quality_context, *checks)
    assert [item.check_id for item in result.executions] == [
        "DQ_TEST_A_PASS",
        "DQ_TEST_B_FAIL",
        "DQ_TEST_C_NA",
        "DQ_TEST_C_NA",
        "DQ_TEST_C_NA",
        "DQ_TEST_D_DISABLED",
    ]
    assert result.summary.model_dump() == {
        "total_executions": 6,
        "executed": 2,
        "passed": 1,
        "failed": 1,
        "skipped": 1,
        "not_applicable": 3,
        "errors": 0,
        "finding_count": 1,
    }
    assert [item.dimension for item in result.dimensions] == list(QualityDimension)
    assert result.metadata.model_dump().keys() == {
        "quality_framework_version",
        "dimension_taxonomy_version",
        "run_reference",
        "configuration_fingerprint",
        "registry_fingerprint",
        "registered_check_count",
        "enabled_check_count",
        "result_count",
    }


def test_run_and_finding_identity_changes_only_for_meaningful_inputs(
    quality_context: QualityCheckContext,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    definition = make_definition("DQ_TEST_IDENTITY")
    base_check = TestCheck(definition, outcome=QualityOutcome.FAIL, severity=Severity.LOW)
    base = run(quality_context, base_check)
    repeated = run(quality_context, base_check)
    assert repeated.metadata.run_reference == base.metadata.run_reference
    assert repeated.executions[0].findings[0].finding_id == (
        base.executions[0].findings[0].finding_id
    )

    version_changed = run(
        quality_context,
        TestCheck(
            make_definition("DQ_TEST_IDENTITY", check_version="1.0.1"),
            outcome=QualityOutcome.FAIL,
            severity=Severity.LOW,
        ),
    )
    assert version_changed.metadata.run_reference != base.metadata.run_reference
    assert version_changed.executions[0].findings[0].finding_id != (
        base.executions[0].findings[0].finding_id
    )

    low_config = QualityFrameworkConfig(
        check_configurations=(
            QualityCheckConfiguration(
                check_id="DQ_TEST_IDENTITY",
                parameters=(QualityConfigParameter(name="threshold", value=1),),
            ),
        )
    )
    high_config = QualityFrameworkConfig(
        check_configurations=(
            QualityCheckConfiguration(
                check_id="DQ_TEST_IDENTITY",
                parameters=(QualityConfigParameter(name="threshold", value=2),),
            ),
        )
    )
    configured_low = run(quality_context, base_check, config=low_config)
    configured_high = run(quality_context, base_check, config=high_config)
    assert configured_low.metadata.run_reference != configured_high.metadata.run_reference
    assert configured_low.executions[0].findings[0].finding_id != (
        configured_high.executions[0].findings[0].finding_id
    )

    registry = QualityCheckRegistry((base_check,))
    original_reference = quality_runner_module._run_reference(
        quality_context, registry, QualityFrameworkConfig()
    )
    monkeypatch.setattr(quality_runner_module, "QUALITY_FRAMEWORK_VERSION", "1.0.1")
    assert (
        quality_runner_module._run_reference(quality_context, registry, QualityFrameworkConfig())
        != original_reference
    )


def test_finding_identity_includes_target_severity_and_evidence(
    quality_context: QualityCheckContext,
) -> None:
    definition = make_definition("DQ_TEST_COLUMN_ID", scope=CheckScope.COLUMN)
    first_target, second_target = quality_context.column_targets()[:2]
    first = run(
        quality_context,
        TestCheck(
            definition,
            outcome=QualityOutcome.FAIL,
            explicit_targets=(first_target,),
        ),
    )
    second = run(
        quality_context,
        TestCheck(
            definition,
            outcome=QualityOutcome.FAIL,
            explicit_targets=(second_target,),
        ),
    )
    assert first.metadata.run_reference == second.metadata.run_reference
    assert first.executions[0].findings[0].finding_id != (
        second.executions[0].findings[0].finding_id
    )

    high = run(
        quality_context,
        TestCheck(definition, outcome=QualityOutcome.FAIL, severity=Severity.HIGH),
    )
    changed_evidence = run(
        quality_context,
        TestCheck(definition, outcome=QualityOutcome.FAIL, evidence_observed=2),
    )
    baseline = run(quality_context, TestCheck(definition, outcome=QualityOutcome.FAIL))
    assert high.metadata.run_reference == baseline.metadata.run_reference
    assert changed_evidence.metadata.run_reference == baseline.metadata.run_reference
    assert high.executions[0].findings[0].finding_id != (
        baseline.executions[0].findings[0].finding_id
    )
    assert changed_evidence.executions[0].findings[0].finding_id != (
        baseline.executions[0].findings[0].finding_id
    )


def test_serialized_result_rejects_finding_and_aggregate_identity_corruption(
    quality_context: QualityCheckContext,
) -> None:
    result = run(
        quality_context,
        TestCheck(make_definition("DQ_TEST_INTEGRITY"), outcome=QualityOutcome.FAIL),
    )
    mismatched_finding = result.model_dump()
    mismatched_finding["executions"][0]["findings"][0]["check_id"] = "DQ_TEST_OTHER"
    with pytest.raises(ValidationError, match="finding identity"):
        type(result).model_validate(mismatched_finding)

    wrong_result_count = result.model_dump()
    wrong_result_count["metadata"]["result_count"] = 2
    with pytest.raises(ValidationError, match="result_count"):
        type(result).model_validate(wrong_result_count)

    wrong_dimensions = result.model_dump()
    wrong_dimensions["dimensions"] = tuple(reversed(wrong_dimensions["dimensions"]))
    with pytest.raises(ValidationError, match="complete taxonomy"):
        type(result).model_validate(wrong_dimensions)

    informational = result.executions[0].findings[0].model_dump()
    informational["severity"] = Severity.INFORMATIONAL
    with pytest.raises(ValidationError, match="informational severity"):
        type(result.executions[0].findings[0]).model_validate(informational)

    non_failure = result.executions[0].findings[0].model_dump()
    non_failure["outcome"] = QualityOutcome.PASS
    with pytest.raises(ValidationError, match="failed outcome"):
        type(result.executions[0].findings[0]).model_validate(non_failure)

    status_details = result.executions[0].model_dump()
    status_details["status_code"] = "INVALID_STATUS"
    status_details["message"] = "Executed results cannot carry status details."
    with pytest.raises(ValidationError, match="status details"):
        type(result.executions[0]).model_validate(status_details)

    missing_findings = result.executions[0].model_dump()
    missing_findings["findings"] = ()
    with pytest.raises(ValidationError, match="require at least one finding"):
        type(result.executions[0]).model_validate(missing_findings)

    mismatched_scope = result.executions[0].model_dump()
    mismatched_scope["scope"] = CheckScope.COLUMN
    with pytest.raises(ValidationError, match="target scope"):
        type(result.executions[0]).model_validate(mismatched_scope)

    pass_with_finding = result.executions[0].model_dump()
    pass_with_finding["outcome"] = QualityOutcome.PASS
    with pytest.raises(ValidationError, match="passed executions"):
        type(result.executions[0]).model_validate(pass_with_finding)

    skipped = run(
        quality_context,
        TestCheck(make_definition("DQ_TEST_SKIPPED_MODEL", default_enabled=False)),
    ).executions[0]
    evaluated_skip = skipped.model_dump()
    evaluated_skip["outcome"] = QualityOutcome.PASS
    with pytest.raises(ValidationError, match="not_evaluated"):
        type(skipped).model_validate(evaluated_skip)
    missing_skip_details = skipped.model_dump()
    missing_skip_details["status_code"] = None
    with pytest.raises(ValidationError, match="require a status code"):
        type(skipped).model_validate(missing_skip_details)

    bad_aggregate = result.model_dump()
    bad_aggregate["summary"]["finding_count"] = 2
    with pytest.raises(ValidationError, match="dimension counts"):
        type(result).model_validate(bad_aggregate)

    bad_run_reference = result.model_dump()
    bad_run_reference["executions"][0]["findings"][0]["run_reference"] = "0" * 64
    with pytest.raises(ValidationError, match="run references"):
        type(result).model_validate(bad_run_reference)

    invalid_metadata = result.metadata.model_dump()
    invalid_metadata["enabled_check_count"] = 2
    with pytest.raises(ValidationError, match="cannot exceed"):
        type(result.metadata).model_validate(invalid_metadata)

    invalid_total = result.summary.model_dump()
    invalid_total["total_executions"] = 2
    with pytest.raises(ValidationError, match="status counts"):
        type(result.summary).model_validate(invalid_total)
    invalid_outcomes = result.summary.model_dump()
    invalid_outcomes["passed"] = 1
    with pytest.raises(ValidationError, match="pass and fail"):
        type(result.summary).model_validate(invalid_outcomes)


def test_typed_framework_errors_are_not_misclassified_as_quality_results(
    quality_context: QualityCheckContext,
) -> None:
    evaluation_error = TestCheck(
        make_definition("DQ_TEST_FRAMEWORK_ERROR"),
        expected_error=lambda: QualityContextError(
            "TEST_CONTEXT_ERROR", "A safe framework context error."
        ),
    )
    with pytest.raises(QualityContextError, match="safe framework"):
        run(quality_context, evaluation_error)

    class TypedConfigurationFailure(TestCheck):
        def validate_configuration(self, configuration: QualityCheckConfiguration | None) -> None:
            del configuration
            raise QualityConfigurationError(
                "TEST_CONFIGURATION_ERROR", "A safe typed configuration error."
            )

    configuration_error = TypedConfigurationFailure(make_definition("DQ_TEST_TYPED_CONFIGURATION"))
    with pytest.raises(QualityConfigurationError, match="safe typed configuration"):
        run(quality_context, configuration_error)


def test_context_rejects_version_and_profile_cardinality_mismatches(
    quality_context: QualityCheckContext,
) -> None:
    version_mismatch = quality_context.dataset_profile.model_copy(
        update={"semantic_inference_version": "9.9.9"}
    )
    with pytest.raises(QualityContextError, match="versions"):
        run(
            QualityCheckContext(
                table=quality_context.table,
                semantic_profile=quality_context.semantic_profile,
                dataset_profile=version_mismatch,
            )
        )

    first = quality_context.dataset_profile.columns[0]
    cardinality_mismatch = quality_context.dataset_profile.model_copy(
        update={
            "columns": (
                first.model_copy(update={"unique_count": (first.unique_count or 0) + 1}),
                *quality_context.dataset_profile.columns[1:],
            )
        }
    )
    with pytest.raises(QualityContextError, match="dataset profile"):
        run(
            QualityCheckContext(
                table=quality_context.table,
                semantic_profile=quality_context.semantic_profile,
                dataset_profile=cardinality_mismatch,
            )
        )
