"""Non-benchmark sanity coverage for quality registry and dispatch scale."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from haralens.profiling import profile_dataset
from haralens.quality import (
    CheckApplicability,
    CheckEvaluation,
    CheckScope,
    QualityCheckConfiguration,
    QualityCheckContext,
    QualityCheckDefinition,
    QualityCheckRegistry,
    QualityCheckRunner,
    QualityDimension,
    QualityFrameworkConfig,
    QualityOutcome,
    QualityResourceLimits,
    QualityTarget,
)
from haralens.semantic import infer_semantic_types


@dataclass
class LightweightColumnCheck:
    definition: QualityCheckDefinition

    def validate_configuration(self, configuration: QualityCheckConfiguration | None) -> None:
        del configuration

    def select_targets(self, context: QualityCheckContext) -> tuple[QualityTarget, ...]:
        return context.column_targets()

    def assess_applicability(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
    ) -> CheckApplicability:
        del context, configuration
        if target.column_position is not None and target.column_position % 2:
            return CheckApplicability(
                applicable=False,
                reason_code="TEST_ODD_COLUMN",
                message="Odd test columns are not applicable.",
            )
        return CheckApplicability(applicable=True)

    def evaluate(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
        resources: QualityResourceLimits,
    ) -> CheckEvaluation:
        del context, target, configuration, resources
        return CheckEvaluation(outcome=QualityOutcome.PASS)


def test_many_checks_columns_filters_and_disabled_dispatch() -> None:
    table = pd.DataFrame({f"column_{index}": range(20) for index in range(40)})
    semantic = infer_semantic_types(table)
    context = QualityCheckContext(
        table=table,
        semantic_profile=semantic,
        dataset_profile=profile_dataset(table, semantic),
    )
    checks = tuple(
        LightweightColumnCheck(
            QualityCheckDefinition(
                check_id=f"DQ_TEST_SCALE_{index:03d}",
                check_version="1.0.0",
                display_name=f"Scale check {index}",
                dimension=(
                    QualityDimension.VALIDITY if index % 2 else QualityDimension.COMPLETENESS
                ),
                scope=CheckScope.COLUMN,
                description="A lightweight dispatch-only test fixture.",
            )
        )
        for index in range(50)
    )
    disabled = tuple(f"DQ_TEST_SCALE_{index:03d}" for index in range(0, 50, 10))
    result = QualityCheckRunner().run(
        context,
        QualityCheckRegistry(reversed(checks)),
        QualityFrameworkConfig(
            disabled_check_ids=disabled,
            included_dimensions=(QualityDimension.COMPLETENESS,),
        ),
    )
    assert result.metadata.registered_check_count == 50
    assert result.metadata.enabled_check_count == 20
    assert result.summary.total_executions == 50 + (20 * 39)
    assert result.summary.executed == 20 * 20
    assert result.summary.not_applicable == 20 * 20
    assert result.summary.skipped == 30
