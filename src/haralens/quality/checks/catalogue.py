"""Production checks. Registration is explicit and has no import side effects."""

# The protocol is fully typed; the compact concrete check implementations intentionally
# share the protocol's runtime signature.
# mypy: disable-error-code="no-untyped-def"

from __future__ import annotations

import math
from dataclasses import dataclass

import pandas as pd

from haralens.quality.config import QualityCheckConfiguration, QualityResourceLimits
from haralens.quality.contracts import QualityCheck, QualityCheckContext
from haralens.quality.models import (
    AffectedPopulation,
    CheckApplicability,
    CheckEvaluation,
    CheckScope,
    ConditionOperator,
    EvidenceSource,
    FindingDraft,
    MethodologyMetadata,
    PopulationBasis,
    QualityCheckDefinition,
    QualityCondition,
    QualityDimension,
    QualityEvidence,
    QualityOutcome,
    QualityTarget,
    Severity,
)
from haralens.quality.registry import QualityCheckRegistry
from haralens.semantic.models import SemanticType

from .config import ProductionQualityConfig


def _severity(pct: float, cfg: ProductionQualityConfig) -> Severity | None:
    if pct <= 0:
        return None
    if pct <= cfg.missingness_low_max:
        return Severity.LOW
    if pct <= cfg.missingness_medium_max:
        return Severity.MEDIUM
    if pct <= cfg.missingness_high_max:
        return Severity.HIGH
    return Severity.CRITICAL


def _evidence(
    metric: str, observed: int | float, source: EvidenceSource = EvidenceSource.TABLE
) -> tuple[QualityEvidence, ...]:
    return (QualityEvidence(metric_name=metric, source=source, observed=observed),)


def _finding(
    severity: Severity,
    message: str,
    *,
    affected: AffectedPopulation | None,
    metric: str,
    observed: int | float,
    target: QualityTarget | None = None,
    source: EvidenceSource = EvidenceSource.TABLE,
    family: str,
    root_cause_group: str | None = None,
) -> FindingDraft:
    del target
    return FindingDraft(
        severity=severity,
        message=message,
        affected_population=affected,
        condition=QualityCondition(
            metric_name=metric,
            operator=ConditionOperator.GREATER_THAN_OR_EQUAL,
            expected=0,
        ),
        evidence=_evidence(metric, observed, source),
        methodology=tuple(
            item
            for item in (
                MethodologyMetadata(name="finding_family", value=family),
                MethodologyMetadata(name="root_cause_group", value=root_cause_group)
                if root_cause_group is not None
                else None,
            )
            if item is not None
        ),
    )


@dataclass(frozen=True)
class _Check:
    definition: QualityCheckDefinition
    defaults: ProductionQualityConfig

    def validate_configuration(self, configuration: QualityCheckConfiguration | None) -> None:
        del configuration

    def select_targets(self, context: QualityCheckContext) -> tuple[QualityTarget, ...]:
        if self.definition.scope is CheckScope.DATASET:
            return (context.dataset_target(),)
        return context.column_targets()

    def assess_applicability(
        self,
        context: QualityCheckContext,
        target: QualityTarget,
        configuration: QualityCheckConfiguration | None,
    ) -> CheckApplicability:
        del configuration
        if self.definition.scope is CheckScope.COLUMN and target.column_position is not None:
            semantic = context.column_semantic(target.column_position).effective_type
            supported = self.definition.supported_semantic_types
            if supported and semantic not in supported:
                return CheckApplicability(
                    applicable=False,
                    reason_code="UNSUPPORTED_SEMANTIC_TYPE",
                    message="The column semantic type is outside this check's scope.",
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


class _DatasetMissingness(_Check):
    def evaluate(self, context, target, configuration, resources):
        del target, resources
        total = int(context.table.size)
        missing = int(context.table.isna().sum().sum())
        pct = missing / total * 100 if total else 0.0
        sev = _severity(pct, self.defaults)
        if sev is None:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    sev,
                    f"{pct:.2f}% of dataset cells are missing.",
                    affected=AffectedPopulation.from_counts(
                        missing, total, PopulationBasis.TOTAL_CELLS
                    ),
                    metric="missing_cell_count",
                    observed=missing,
                    family="completeness_missingness",
                ),
            ),
        )


class _ColumnMissingness(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        missing = int(context.column(pos).isna().sum())
        total = len(context.table)
        if missing == total:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        pct = missing / total * 100 if total else 0.0
        sev = _severity(pct, self.defaults)
        if sev is None:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    sev,
                    f"{pct:.2f}% of values in this column are missing.",
                    affected=AffectedPopulation.from_counts(
                        missing, total, PopulationBasis.TOTAL_ROWS
                    ),
                    metric="missing_row_count",
                    observed=missing,
                    family="completeness_missingness",
                    root_cause_group=(
                        "identifier_missingness"
                        if context.column_semantic(pos).effective_type is SemanticType.IDENTIFIER
                        else None
                    ),
                ),
            ),
        )


class _EmptyColumn(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        total = len(context.table)
        if total == 0 or int(context.column(pos).notna().sum()) == 0:
            return CheckEvaluation(
                outcome=QualityOutcome.FAIL,
                findings=(
                    _finding(
                        Severity.HIGH,
                        "This column contains no observed values.",
                        affected=AffectedPopulation.from_counts(
                            total, total, PopulationBasis.TOTAL_ROWS
                        ),
                        metric="observed_value_count",
                        observed=0,
                        family="empty_column",
                    ),
                ),
            )
        return CheckEvaluation(outcome=QualityOutcome.PASS)


class _DuplicateRows(_Check):
    def evaluate(self, context, target, configuration, resources):
        del target, configuration, resources
        rows = len(context.table)
        dup = int(context.table.duplicated(keep="first").sum())
        if not dup:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        pct = dup / rows * 100 if rows else 0.0
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    _severity(pct, self.defaults) or Severity.LOW,
                    f"{dup} duplicate row occurrence(s) appear beyond the first copy.",
                    affected=AffectedPopulation.from_counts(dup, rows, PopulationBasis.TOTAL_ROWS),
                    metric="duplicate_row_count",
                    observed=dup,
                    family="duplicate_rows",
                ),
            ),
        )


class _IdentifierUniqueness(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        series = context.column(pos)
        non_null = int(series.notna().sum())
        duplicates = int(series.dropna().duplicated(keep="first").sum())
        if not duplicates:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        pct = duplicates / non_null * 100 if non_null else 0.0
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    _severity(pct, self.defaults) or Severity.LOW,
                    "Identifier values are duplicated among non-null observations.",
                    affected=AffectedPopulation.from_counts(
                        duplicates, non_null, PopulationBasis.NON_NULL_ROWS
                    ),
                    metric="duplicate_identifier_count",
                    observed=duplicates,
                    family="identifier_uniqueness",
                ),
            ),
        )


class _NonFinite(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        if pos is None:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        numeric = context.column(pos)
        count = 0
        for value in numeric.to_numpy().flat:
            if not pd.isna(value) and not math.isfinite(float(value)):
                count += 1
        if not count:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        total = len(numeric)
        pct = count / total * 100 if total else 0
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    _severity(pct, self.defaults) or Severity.LOW,
                    "Non-finite numeric values were detected in this numeric column.",
                    affected=AffectedPopulation.from_counts(
                        count, total, PopulationBasis.CUSTOM, basis_description="numeric cells"
                    ),
                    metric="nonfinite_numeric_count",
                    observed=count,
                    family="nonfinite_numeric",
                ),
            ),
        )


class _ColumnWhitespace(_Check):
    def evaluate(self, context, target, configuration, resources):
        del target, configuration, resources
        count = sum(isinstance(c, str) and c != c.strip() for c in context.table.columns)
        if not count:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    Severity.MEDIUM,
                    f"{count} column label(s) contain leading or trailing whitespace.",
                    affected=AffectedPopulation.from_counts(
                        count,
                        len(context.table.columns),
                        PopulationBasis.CUSTOM,
                        basis_description="column labels",
                    ),
                    metric="whitespace_column_count",
                    observed=count,
                    family="column_label_consistency",
                ),
            ),
        )


class _CategoryNormalization(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        values = context.column(pos).dropna()
        if values.empty:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        normalized = values.map(lambda x: str(x).strip().casefold())
        groups = [
            group
            for _, group in pd.DataFrame({"n": normalized, "o": values}).groupby("n", sort=True)
            if group["o"].nunique(dropna=False) > 1
        ]
        collision_groups = len(groups)
        affected_rows = sum(len(group) for group in groups)
        if not collision_groups:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    Severity.LOW,
                    "Distinct categorical representations collapse under trim-and-case "
                    "normalization.",
                    affected=AffectedPopulation.from_counts(
                        affected_rows, len(values), PopulationBasis.NON_NULL_ROWS
                    ),
                    metric="affected_category_row_count",
                    observed=affected_rows,
                    family="category_consistency",
                ),
            ),
        )


class _Constant(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        non_null = context.column(pos).dropna()
        if (
            len(context.table) <= 1
            or not len(non_null)
            or context.column_semantic(pos).effective_type is SemanticType.IDENTIFIER
        ):
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        if len(non_null) <= 1 or non_null.nunique(dropna=False) <= 1:
            return CheckEvaluation(
                outcome=QualityOutcome.FAIL,
                findings=(
                    _finding(
                        Severity.MEDIUM,
                        "This column has no observed variance.",
                        affected=None,
                        metric="distinct_value_count",
                        observed=int(non_null.nunique(dropna=False)),
                        family="constant_column",
                    ),
                ),
            )
        return CheckEvaluation(outcome=QualityOutcome.PASS)


class _HighCardinality(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        semantic = context.column_semantic(pos).effective_type
        if semantic is SemanticType.IDENTIFIER:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        series = context.column(pos).dropna()
        if len(series) < self.defaults.high_cardinality_min_observations:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        ratio = series.nunique(dropna=False) / len(series) if len(series) else 0
        if ratio < self.defaults.high_cardinality_ratio:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    Severity.MEDIUM,
                    "This categorical column has very high cardinality for its observed values.",
                    affected=None,
                    metric="cardinality_ratio",
                    observed=ratio,
                    family="high_cardinality",
                ),
            ),
        )


class _IdentifierMissingness(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        series = context.column(pos)
        missing = int(series.isna().sum())
        total = len(series)
        if not missing:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        pct = missing / total * 100 if total else 0
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    _severity(pct, self.defaults) or Severity.LOW,
                    "Identifier values are missing.",
                    affected=AffectedPopulation.from_counts(
                        missing, total, PopulationBasis.TOTAL_ROWS
                    ),
                    metric="missing_identifier_count",
                    observed=missing,
                    family="identifier_missingness",
                    root_cause_group="identifier_missingness",
                ),
            ),
        )


class _UnknownSemantic(_Check):
    def evaluate(self, context, target, configuration, resources):
        del configuration, resources
        pos = target.column_position
        assert pos is not None  # noqa: S101
        col = context.column_semantic(pos)
        if col.effective_type is not SemanticType.UNKNOWN:
            return CheckEvaluation(outcome=QualityOutcome.PASS)
        return CheckEvaluation(
            outcome=QualityOutcome.FAIL,
            findings=(
                _finding(
                    Severity.LOW,
                    "The column's semantic interpretation is uncertain; review it before "
                    "downstream analysis.",
                    affected=None,
                    metric="semantic_confidence_low",
                    observed=1,
                    family="semantic_readiness",
                ),
            ),
        )


def _definition(
    check_id: str,
    name: str,
    dimension: QualityDimension,
    scope: CheckScope,
    description: str,
    supported: tuple[SemanticType, ...] = (),
) -> QualityCheckDefinition:
    return QualityCheckDefinition(
        check_id=check_id,
        check_version="1.0.0",
        display_name=name,
        dimension=dimension,
        scope=scope,
        description=description,
        supported_semantic_types=supported,
        tags=("production", "v0_1"),
    )


def create_default_quality_registry(
    config: ProductionQualityConfig | None = None,
) -> QualityCheckRegistry:
    cfg = config or ProductionQualityConfig()
    checks: list[QualityCheck] = [
        _DatasetMissingness(
            _definition(
                "DQ_COMPLETENESS_DATASET_MISSINGNESS",
                "Dataset missingness",
                QualityDimension.COMPLETENESS,
                CheckScope.DATASET,
                "Measures missing cells across the table.",
            ),
            cfg,
        ),
        _ColumnMissingness(
            _definition(
                "DQ_COMPLETENESS_COLUMN_MISSINGNESS",
                "Column missingness",
                QualityDimension.COMPLETENESS,
                CheckScope.COLUMN,
                "Measures missing observations per column.",
            ),
            cfg,
        ),
        _EmptyColumn(
            _definition(
                "DQ_COMPLETENESS_EMPTY_COLUMN",
                "Empty column",
                QualityDimension.COMPLETENESS,
                CheckScope.COLUMN,
                "Detects columns with no observed values.",
            ),
            cfg,
        ),
        _DuplicateRows(
            _definition(
                "DQ_UNIQUENESS_DUPLICATE_ROWS",
                "Duplicate rows",
                QualityDimension.UNIQUENESS,
                CheckScope.DATASET,
                "Counts duplicate row occurrences beyond the first.",
            ),
            cfg,
        ),
        _IdentifierUniqueness(
            _definition(
                "DQ_UNIQUENESS_IDENTIFIER_VALUES",
                "Identifier uniqueness",
                QualityDimension.UNIQUENESS,
                CheckScope.COLUMN,
                "Checks non-null identifier values for duplicates.",
                (SemanticType.IDENTIFIER,),
            ),
            cfg,
        ),
        _NonFinite(
            _definition(
                "DQ_VALIDITY_NONFINITE_NUMERIC",
                "Non-finite numeric values",
                QualityDimension.VALIDITY,
                CheckScope.COLUMN,
                "Detects positive and negative infinity in numeric cells.",
                (SemanticType.NUMERIC_CONTINUOUS, SemanticType.NUMERIC_DISCRETE),
            ),
            cfg,
        ),
        _ColumnWhitespace(
            _definition(
                "DQ_CONSISTENCY_COLUMN_NAME_WHITESPACE",
                "Column-name whitespace",
                QualityDimension.CONSISTENCY,
                CheckScope.DATASET,
                "Detects surrounding whitespace in column labels.",
            ),
            cfg,
        ),
        _CategoryNormalization(
            _definition(
                "DQ_CONSISTENCY_CATEGORY_NORMALIZATION",
                "Category normalization collisions",
                QualityDimension.CONSISTENCY,
                CheckScope.COLUMN,
                "Detects conservative trim-and-case category collisions.",
                (SemanticType.CATEGORICAL,),
            ),
            cfg,
        ),
        _IdentifierMissingness(
            _definition(
                "DQ_INTEGRITY_IDENTIFIER_MISSINGNESS",
                "Identifier missingness",
                QualityDimension.INTEGRITY,
                CheckScope.COLUMN,
                "Detects missing identifier values.",
                (SemanticType.IDENTIFIER,),
            ),
            cfg,
        ),
        _Constant(
            _definition(
                "DQ_READINESS_CONSTANT_COLUMN",
                "Constant column",
                QualityDimension.ANALYTICAL_READINESS,
                CheckScope.COLUMN,
                "Detects columns with no observed variance.",
            ),
            cfg,
        ),
        _HighCardinality(
            _definition(
                "DQ_READINESS_HIGH_CARDINALITY",
                "High-cardinality categorical column",
                QualityDimension.ANALYTICAL_READINESS,
                CheckScope.COLUMN,
                "Detects non-identifier categorical columns with high cardinality.",
                (SemanticType.CATEGORICAL,),
            ),
            cfg,
        ),
    ]
    return QualityCheckRegistry(checks)
