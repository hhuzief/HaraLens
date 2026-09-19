"""Typed check protocol and immutable upstream context."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

import pandas as pd

from haralens.ingestion.models import IngestionMetadata
from haralens.profiling.models import ColumnProfile, DatasetProfile
from haralens.quality.config import (
    QualityCheckConfiguration,
    QualityResourceLimits,
)
from haralens.quality.models import (
    CheckApplicability,
    CheckEvaluation,
    CheckScope,
    QualityCheckDefinition,
    QualityTarget,
)
from haralens.semantic.models import ColumnSemanticInference, DatasetSemanticProfile


@dataclass(frozen=True, slots=True)
class QualityCheckContext:
    """Trusted, read-only-by-contract inputs supplied to independent checks."""

    table: pd.DataFrame
    semantic_profile: DatasetSemanticProfile
    dataset_profile: DatasetProfile
    ingestion_metadata: IngestionMetadata | None = None

    def dataset_target(self) -> QualityTarget:
        return QualityTarget(scope=CheckScope.DATASET)

    def column_targets(self) -> tuple[QualityTarget, ...]:
        return tuple(
            QualityTarget(
                scope=CheckScope.COLUMN,
                column_name=column.column_name,
                column_position=column.column_position,
            )
            for column in self.dataset_profile.columns
        )

    def column_semantic(self, position: int) -> ColumnSemanticInference:
        return self.semantic_profile.columns[position]

    def column_profile(self, position: int) -> ColumnProfile:
        return self.dataset_profile.columns[position]

    def column(self, position: int) -> pd.Series[Any]:
        return self.table.iloc[:, position]


class QualityCheck(Protocol):
    """Small interface implemented independently by each future production check."""

    @property
    def definition(self) -> QualityCheckDefinition: ...

    def validate_configuration(self, configuration: QualityCheckConfiguration | None) -> None: ...

    def select_targets(self, context: QualityCheckContext) -> tuple[QualityTarget, ...]: ...

    def assess_applicability(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
    ) -> CheckApplicability: ...

    def evaluate(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
        resources: QualityResourceLimits,
    ) -> CheckEvaluation: ...
