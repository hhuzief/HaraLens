"""Deterministic execution engine for independently implemented quality checks."""

from __future__ import annotations

import hashlib
import json
import logging
from collections import Counter
from typing import Any, NoReturn

from haralens.profiling.models import CategoricalStatistics
from haralens.quality.config import QualityCheckConfiguration, QualityFrameworkConfig
from haralens.quality.contracts import QualityCheckContext
from haralens.quality.errors import (
    CheckDataUnsupportedError,
    CheckPrerequisiteError,
    CheckResourceLimitError,
    QualityConfigurationError,
    QualityContextError,
    QualityFrameworkError,
    QualityResourceError,
    UnexpectedCheckError,
)
from haralens.quality.models import (
    QUALITY_FRAMEWORK_VERSION,
    CheckExecutionResult,
    CheckExecutionStatus,
    CheckPrerequisite,
    CheckScope,
    DimensionRunSummary,
    FindingDraft,
    QualityCheckDefinition,
    QualityDimension,
    QualityFinding,
    QualityOutcome,
    QualityRunMetadata,
    QualityRunResult,
    QualityRunSummary,
    QualityTarget,
)
from haralens.quality.registry import QualityCheckRegistry, RegisteredQualityCheck

logger = logging.getLogger(__name__)


def _isolated_check_context(context: QualityCheckContext) -> QualityCheckContext:
    """Return a per-check pandas copy-on-write snapshot of the trusted table."""

    return QualityCheckContext(
        table=context.table.copy(deep=False),
        semantic_profile=context.semantic_profile,
        dataset_profile=context.dataset_profile,
        ingestion_metadata=context.ingestion_metadata,
    )


class QualityCheckRunner:
    """Validate trusted inputs, dispatch checks, and build a neutral result."""

    def run(
        self,
        context: QualityCheckContext,
        registry: QualityCheckRegistry,
        config: QualityFrameworkConfig | None = None,
    ) -> QualityRunResult:
        effective_config = config or QualityFrameworkConfig()
        validate_quality_context(context)
        self._validate_registry_and_config(registry, effective_config)

        run_reference = _run_reference(context, registry, effective_config)
        results: list[CheckExecutionResult] = []
        enabled_count = 0

        for entry in registry.entries:
            if len(results) >= effective_config.resources.max_total_executions:
                raise QualityResourceError(
                    "EXECUTION_LIMIT_EXCEEDED",
                    "The configured total execution budget would be exceeded.",
                )
            definition = entry.definition
            check_config = effective_config.configuration_for(definition.check_id)
            configuration_fingerprint = _check_configuration_fingerprint(definition, check_config)
            enabled, disabled_code, disabled_message = _enabled_state(definition, effective_config)
            if not enabled:
                results.append(
                    _unexecuted_result(
                        definition,
                        None,
                        CheckExecutionStatus.SKIPPED,
                        configuration_fingerprint,
                        disabled_code,
                        disabled_message,
                    )
                )
                continue
            enabled_count += 1
            self._validate_check_configuration(entry, check_config)

            # pandas 3 copy-on-write gives each check its own logical table snapshot without
            # eagerly copying every data block. DataFrame API writes detach only that check.
            check_context = _isolated_check_context(context)

            missing = _missing_prerequisite(definition, check_context)
            if missing is not None:
                results.append(
                    _unexecuted_result(
                        definition,
                        None,
                        CheckExecutionStatus.SKIPPED,
                        configuration_fingerprint,
                        "PREREQUISITE_UNAVAILABLE",
                        f"Required capability is unavailable: {missing.value}.",
                    )
                )
                continue

            try:
                targets = entry.check.select_targets(check_context)
                targets = _validated_targets(definition, targets, check_context)
            except Exception as error:
                result = self._failure_result(
                    error,
                    definition,
                    None,
                    configuration_fingerprint,
                    effective_config,
                )
                results.append(result)
                continue

            if len(targets) > effective_config.resources.max_targets_per_check:
                results.append(
                    _unexecuted_result(
                        definition,
                        None,
                        CheckExecutionStatus.SKIPPED,
                        configuration_fingerprint,
                        "TARGET_LIMIT_EXCEEDED",
                        "The configured target budget prevented check execution.",
                    )
                )
                continue
            if not targets:
                results.append(
                    _unexecuted_result(
                        definition,
                        None,
                        CheckExecutionStatus.NOT_APPLICABLE,
                        configuration_fingerprint,
                        "NO_TARGETS",
                        "The check selected no applicable targets.",
                    )
                )
                continue

            if len(results) + len(targets) > effective_config.resources.max_total_executions:
                raise QualityResourceError(
                    "EXECUTION_LIMIT_EXCEEDED",
                    "The configured total execution budget would be exceeded.",
                )
            for target in targets:
                results.append(
                    self._execute_target(
                        entry,
                        target,
                        check_context,
                        check_config,
                        configuration_fingerprint,
                        run_reference,
                        effective_config,
                    )
                )

        execution_tuple = tuple(results)
        return QualityRunResult(
            executions=execution_tuple,
            summary=_summary(execution_tuple),
            dimensions=tuple(
                _dimension_summary(dimension, execution_tuple) for dimension in QualityDimension
            ),
            metadata=QualityRunMetadata(
                run_reference=run_reference,
                configuration_fingerprint=effective_config.fingerprint,
                registry_fingerprint=registry.fingerprint,
                registered_check_count=len(registry),
                enabled_check_count=enabled_count,
                result_count=len(execution_tuple),
            ),
        )

    def _validate_registry_and_config(
        self, registry: QualityCheckRegistry, config: QualityFrameworkConfig
    ) -> None:
        if len(registry) > config.resources.max_registered_checks:
            raise QualityResourceError(
                "REGISTRY_LIMIT_EXCEEDED",
                "The configured registered-check budget is exceeded.",
            )
        registered = {item.definition.check_id for item in registry.entries}
        configured = (
            set(config.enabled_check_ids)
            | set(config.disabled_check_ids)
            | {item.check_id for item in config.check_configurations}
        )
        unknown = sorted(configured - registered)
        if unknown:
            raise QualityConfigurationError(
                "UNKNOWN_CHECK_ID",
                f"Quality configuration references unknown check ID: {unknown[0]}",
            )

    def _validate_check_configuration(
        self,
        entry: RegisteredQualityCheck,
        configuration: QualityCheckConfiguration | None,
    ) -> None:
        try:
            entry.check.validate_configuration(configuration)
        except QualityConfigurationError:
            raise
        except Exception:
            raise QualityConfigurationError(
                "INVALID_CHECK_CONFIGURATION",
                f"Configuration validation failed for {entry.definition.check_id}.",
            ) from None

    def _execute_target(
        self,
        entry: RegisteredQualityCheck,
        target: QualityTarget,
        context: QualityCheckContext,
        check_config: QualityCheckConfiguration | None,
        configuration_fingerprint: str,
        run_reference: str,
        config: QualityFrameworkConfig,
    ) -> CheckExecutionResult:
        definition = entry.definition
        try:
            applicability = entry.check.assess_applicability(context, target, check_config)
            if not applicability.applicable:
                return _unexecuted_result(
                    definition,
                    target,
                    CheckExecutionStatus.NOT_APPLICABLE,
                    configuration_fingerprint,
                    applicability.reason_code or "NOT_APPLICABLE",
                    applicability.message or "The check does not apply to this target.",
                )
            evaluation = entry.check.evaluate(
                context,
                target,
                check_config,
                config.resources,
            )
            findings = tuple(
                _materialize_finding(
                    draft,
                    definition,
                    target,
                    run_reference,
                    configuration_fingerprint,
                    index,
                )
                for index, draft in enumerate(evaluation.findings)
            )
            return CheckExecutionResult(
                check_id=definition.check_id,
                check_version=definition.check_version,
                dimension=definition.dimension,
                scope=definition.scope,
                target=target,
                execution_status=CheckExecutionStatus.EXECUTED,
                outcome=evaluation.outcome,
                findings=findings,
                configuration_fingerprint=configuration_fingerprint,
            )
        except Exception as error:
            return self._failure_result(
                error,
                definition,
                target,
                configuration_fingerprint,
                config,
            )

    def _failure_result(
        self,
        error: Exception,
        definition: QualityCheckDefinition,
        target: QualityTarget | None,
        configuration_fingerprint: str,
        config: QualityFrameworkConfig,
    ) -> CheckExecutionResult:
        if isinstance(error, (CheckPrerequisiteError, CheckResourceLimitError)):
            return _unexecuted_result(
                definition,
                target,
                CheckExecutionStatus.SKIPPED,
                configuration_fingerprint,
                error.code,
                error.message,
            )
        if isinstance(error, CheckDataUnsupportedError):
            return _unexecuted_result(
                definition,
                target,
                CheckExecutionStatus.NOT_APPLICABLE,
                configuration_fingerprint,
                error.code,
                error.message,
            )
        if isinstance(error, UnexpectedCheckError):
            safe_message = error.message
            safe_code = error.code
            if config.fail_fast_internal_errors:
                raise error
            return _unexecuted_result(
                definition,
                target,
                CheckExecutionStatus.ERROR,
                configuration_fingerprint,
                safe_code,
                safe_message,
            )
        if isinstance(error, QualityFrameworkError):
            raise error
        safe_message = "The check encountered an internal implementation error."
        logger.error(
            "Quality check internal error",
            extra={
                "quality_check_id": definition.check_id,
                "quality_check_version": definition.check_version,
                "quality_dimension": definition.dimension.value,
                "quality_column_position": (target.column_position if target is not None else None),
                "quality_error_code": "INTERNAL_CHECK_ERROR",
            },
        )
        if config.fail_fast_internal_errors:
            raise UnexpectedCheckError("INTERNAL_CHECK_ERROR", safe_message) from None
        return _unexecuted_result(
            definition,
            target,
            CheckExecutionStatus.ERROR,
            configuration_fingerprint,
            "INTERNAL_CHECK_ERROR",
            safe_message,
        )


def validate_quality_context(context: QualityCheckContext) -> None:
    """Reject upstream artifacts that do not describe the supplied physical table."""

    table = context.table
    semantic = context.semantic_profile
    profile = context.dataset_profile
    rows, columns = table.shape
    if (
        semantic.run_metadata.total_rows != rows
        or semantic.run_metadata.total_columns != columns
        or profile.run_metadata.total_rows != rows
        or profile.run_metadata.total_columns != columns
        or profile.summary.row_count != rows
        or profile.summary.column_count != columns
        or profile.summary.cell_count != rows * columns
        or len(semantic.columns) != columns
        or len(profile.columns) != columns
    ):
        _context_error("QUALITY_CONTEXT_SHAPE_MISMATCH", "Quality inputs have inconsistent shapes.")
    if profile.semantic_inference_version != semantic.inference_version:
        _context_error(
            "QUALITY_CONTEXT_VERSION_MISMATCH",
            "Profiling and semantic inference versions are inconsistent.",
        )

    missing_cells = 0
    for position in range(columns):
        series = table.iloc[:, position]
        name = _safe_column_name(table.columns[position], position)
        null_count = int(series.isna().sum())
        missing_cells += null_count
        semantic_column = semantic.columns[position]
        profile_column = profile.columns[position]
        common_matches = (
            semantic_column.column_position == position
            and profile_column.column_position == position
            and semantic_column.column_name == name
            and profile_column.column_name == name
            and semantic_column.physical_dtype == str(series.dtype)
            and profile_column.physical_dtype == str(series.dtype)
            and semantic_column.total_count == rows
            and profile_column.total_count == rows
            and semantic_column.null_count == null_count
            and profile_column.null_count == null_count
            and semantic_column.non_null_count == rows - null_count
            and profile_column.non_null_count == rows - null_count
            and profile_column.inferred_semantic_type == semantic_column.semantic_type
            and profile_column.semantic_type == semantic_column.effective_type
            and profile_column.semantic_confidence == semantic_column.confidence
        )
        if not common_matches:
            _context_error(
                "QUALITY_CONTEXT_COLUMN_MISMATCH",
                "A quality input column does not match the supplied table.",
            )
        if semantic_column.unique_count is not None:
            try:
                unique_count = int(series.nunique(dropna=True))
            except (TypeError, ValueError):
                unique_count = None
            if unique_count != semantic_column.unique_count:
                _context_error(
                    "QUALITY_CONTEXT_STALE_SEMANTIC",
                    "The semantic profile is stale for the supplied table.",
                )
        expected_profile_unique = semantic_column.unique_count
        if isinstance(profile_column.statistics, CategoricalStatistics):
            expected_profile_unique = profile_column.statistics.category_count
        if profile_column.unique_count != expected_profile_unique:
            _context_error(
                "QUALITY_CONTEXT_STALE_PROFILE",
                "The dataset profile is inconsistent with semantic inference.",
            )
    if profile.summary.missing_cell_count != missing_cells:
        _context_error(
            "QUALITY_CONTEXT_STALE_PROFILE",
            "The dataset summary is stale for the supplied table.",
        )


def _validated_targets(
    definition: QualityCheckDefinition,
    targets: object,
    context: QualityCheckContext,
) -> tuple[QualityTarget, ...]:
    if not isinstance(targets, tuple) or not all(
        isinstance(item, QualityTarget) for item in targets
    ):
        raise UnexpectedCheckError(
            "INVALID_CHECK_TARGETS", "A check returned an invalid target collection."
        )
    if not targets:
        return ()
    seen: set[str] = set()
    validated: list[QualityTarget] = []
    for target in targets:
        if target.scope is not definition.scope:
            raise UnexpectedCheckError(
                "INVALID_CHECK_TARGET", "A check returned a target with the wrong scope."
            )
        _validate_target_against_context(target, context)
        key = _canonical_json(target.model_dump(mode="json"))
        if key in seen:
            raise UnexpectedCheckError(
                "DUPLICATE_CHECK_TARGET", "A check returned the same target more than once."
            )
        seen.add(key)
        validated.append(target)
    return tuple(sorted(validated, key=_target_sort_key))


def _validate_target_against_context(target: QualityTarget, context: QualityCheckContext) -> None:
    if target.scope is CheckScope.DATASET:
        return
    pairs: tuple[tuple[int, str], ...]
    if target.scope is CheckScope.COLUMN:
        if target.column_position is None or target.column_name is None:
            raise UnexpectedCheckError("INVALID_CHECK_TARGET", "A column target is incomplete.")
        pairs = ((target.column_position, target.column_name),)
    else:
        pairs = tuple(zip(target.column_positions, target.column_names, strict=True))
    for position, name in pairs:
        if position >= len(context.dataset_profile.columns):
            raise UnexpectedCheckError(
                "INVALID_CHECK_TARGET", "A check targeted a column outside the table."
            )
        column = context.dataset_profile.columns[position]
        if column.column_name != name:
            raise UnexpectedCheckError(
                "INVALID_CHECK_TARGET", "A check target does not match the physical column."
            )


def _materialize_finding(
    draft: FindingDraft,
    definition: QualityCheckDefinition,
    target: QualityTarget,
    run_reference: str,
    configuration_fingerprint: str,
    index: int,
) -> QualityFinding:
    payload = {
        "run_reference": run_reference,
        "check_id": definition.check_id,
        "check_version": definition.check_version,
        "target": target.model_dump(mode="json"),
        "configuration_fingerprint": configuration_fingerprint,
        "draft": draft.model_dump(mode="json"),
        "index": index,
    }
    return QualityFinding(
        finding_id=_fingerprint(payload),
        run_reference=run_reference,
        check_id=definition.check_id,
        check_version=definition.check_version,
        dimension=definition.dimension,
        scope=definition.scope,
        target=target,
        outcome=QualityOutcome.FAIL,
        **draft.model_dump(),
    )


def _unexecuted_result(
    definition: QualityCheckDefinition,
    target: QualityTarget | None,
    status: CheckExecutionStatus,
    configuration_fingerprint: str,
    code: str,
    message: str,
) -> CheckExecutionResult:
    return CheckExecutionResult(
        check_id=definition.check_id,
        check_version=definition.check_version,
        dimension=definition.dimension,
        scope=definition.scope,
        target=target,
        execution_status=status,
        outcome=QualityOutcome.NOT_EVALUATED,
        configuration_fingerprint=configuration_fingerprint,
        status_code=code,
        message=message,
    )


def _enabled_state(
    definition: QualityCheckDefinition, config: QualityFrameworkConfig
) -> tuple[bool, str, str]:
    if definition.check_id in config.disabled_check_ids:
        return False, "CHECK_DISABLED", "The check is disabled by configuration."
    if config.included_dimensions and definition.dimension not in config.included_dimensions:
        return False, "DIMENSION_FILTERED", "The check dimension is excluded by configuration."
    if definition.check_id in config.enabled_check_ids:
        return True, "", ""
    if not definition.default_enabled:
        return False, "CHECK_DISABLED", "The check is disabled by default."
    return True, "", ""


def _missing_prerequisite(
    definition: QualityCheckDefinition, context: QualityCheckContext
) -> CheckPrerequisite | None:
    if (
        CheckPrerequisite.INGESTION_METADATA in definition.prerequisites
        and context.ingestion_metadata is None
    ):
        return CheckPrerequisite.INGESTION_METADATA
    return None


def _summary(executions: tuple[CheckExecutionResult, ...]) -> QualityRunSummary:
    values = _counts(executions)
    return QualityRunSummary(**values)


def _dimension_summary(
    dimension: QualityDimension, executions: tuple[CheckExecutionResult, ...]
) -> DimensionRunSummary:
    selected = tuple(item for item in executions if item.dimension is dimension)
    return DimensionRunSummary(dimension=dimension, **_counts(selected))


def _counts(executions: tuple[CheckExecutionResult, ...]) -> dict[str, int]:
    statuses = Counter(item.execution_status for item in executions)
    outcomes = Counter(item.outcome for item in executions)
    return {
        "total_executions": len(executions),
        "executed": statuses[CheckExecutionStatus.EXECUTED],
        "passed": outcomes[QualityOutcome.PASS],
        "failed": outcomes[QualityOutcome.FAIL],
        "skipped": statuses[CheckExecutionStatus.SKIPPED],
        "not_applicable": statuses[CheckExecutionStatus.NOT_APPLICABLE],
        "errors": statuses[CheckExecutionStatus.ERROR],
        "finding_count": sum(len(item.findings) for item in executions),
    }


def _run_reference(
    context: QualityCheckContext,
    registry: QualityCheckRegistry,
    config: QualityFrameworkConfig,
) -> str:
    return _fingerprint(
        {
            "framework_version": QUALITY_FRAMEWORK_VERSION,
            "registry_fingerprint": registry.fingerprint,
            "configuration_fingerprint": config.fingerprint,
            "semantic_profile": context.semantic_profile.model_dump(mode="json"),
            "dataset_profile": context.dataset_profile.model_dump(mode="json"),
        }
    )


def _check_configuration_fingerprint(
    definition: QualityCheckDefinition,
    configuration: QualityCheckConfiguration | None,
) -> str:
    return _fingerprint(
        {
            "check_id": definition.check_id,
            "configuration": (
                configuration.model_dump(mode="json") if configuration is not None else None
            ),
        }
    )


def _target_sort_key(target: QualityTarget) -> tuple[int, tuple[int, ...]]:
    if target.scope is CheckScope.DATASET:
        return 0, ()
    if target.scope is CheckScope.COLUMN:
        position = target.column_position
        if position is None:
            return 1, ()
        return 1, (position,)
    return 2, target.column_positions


def _fingerprint(value: object) -> str:
    return hashlib.sha256(_canonical_json(value).encode("utf-8")).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        allow_nan=False,
    )


def _safe_column_name(label: Any, position: int) -> str:
    try:
        return str(label)
    except Exception:
        return f"column_{position}"


def _context_error(code: str, message: str) -> NoReturn:
    raise QualityContextError(code, message)
