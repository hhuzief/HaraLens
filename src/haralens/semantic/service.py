"""Dataset-level semantic inference service."""

from __future__ import annotations

from collections import Counter
from typing import Any, Literal

import pandas as pd

from haralens.ingestion.models import IngestionResult
from haralens.semantic.config import SemanticInferenceConfig
from haralens.semantic.engine import SemanticInferenceEngine
from haralens.semantic.models import (
    DatasetSemanticProfile,
    InferenceRunMetadata,
    InferenceWarning,
    InferenceWarningCode,
    SemanticType,
    SemanticTypeCount,
)


class SemanticInferenceService:
    """Infer every column independently while preserving order and isolating failures."""

    def __init__(self, config: SemanticInferenceConfig | None = None) -> None:
        self.config = config or SemanticInferenceConfig()
        self._engine = SemanticInferenceEngine(self.config)

    def infer(self, source: pd.DataFrame | IngestionResult) -> DatasetSemanticProfile:
        if isinstance(source, IngestionResult):
            table = source.table
            source_kind: Literal["dataframe", "ingestion_result"] = "ingestion_result"
        else:
            table = source
            source_kind = "dataframe"

        results = []
        dataset_warnings: list[InferenceWarning] = []
        failed_count = 0
        for position, label in enumerate(table.columns):
            column_name = _safe_column_name(label, position)
            series = table.iloc[:, position]
            try:
                result = self._engine.infer_column(column_name, position, series)
            except Exception:  # A pathological object must not abort other columns.
                result = self._engine.failure_result(column_name, position, series)
                failed_count += 1
                dataset_warnings.append(
                    InferenceWarning(
                        code=InferenceWarningCode.COLUMN_INFERENCE_FAILED,
                        message="A column failed inference and was isolated as unknown.",
                        column_position=position,
                    )
                )
            results.append(result)

        counts = Counter(result.semantic_type for result in results)
        type_counts = tuple(
            SemanticTypeCount(semantic_type=semantic_type, count=counts[semantic_type])
            for semantic_type in SemanticType
            if counts[semantic_type]
        )
        return DatasetSemanticProfile(
            columns=tuple(results),
            semantic_type_counts=type_counts,
            configuration=self.config,
            run_metadata=InferenceRunMetadata(
                source_kind=source_kind,
                total_rows=len(table),
                total_columns=len(table.columns),
                sampled_column_count=sum(result.sampled for result in results),
                failed_column_count=failed_count,
            ),
            warnings=tuple(dataset_warnings),
        )


def infer_semantic_types(
    source: pd.DataFrame | IngestionResult,
    config: SemanticInferenceConfig | None = None,
) -> DatasetSemanticProfile:
    """Convenience API for one deterministic dataset inference run."""

    return SemanticInferenceService(config).infer(source)


def _safe_column_name(label: Any, position: int) -> str:
    try:
        return str(label)
    except Exception:
        return f"column_{position}"
