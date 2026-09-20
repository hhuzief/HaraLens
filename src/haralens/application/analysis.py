"""Canonical Gate 2 analysis orchestration path."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import PurePath
from typing import cast

from haralens.analytics import AnalyticsResult, analyze_frame
from haralens.common.config import Settings
from haralens.ingestion import (
    CsvIngestionAdapter,
    IngestionAdapter,
    IngestionRequest,
    IngestionResult,
    ParquetIngestionAdapter,
    SourceType,
    XlsxIngestionAdapter,
)
from haralens.insights import InsightResult, generate_insights
from haralens.profiling import DatasetProfile, profile_dataset
from haralens.quality import (
    QualityCheckContext,
    QualityCheckRunner,
    QualityFrameworkConfig,
    QualityRunResult,
    create_default_quality_registry,
)
from haralens.readiness import AIReadinessResult, assess_readiness
from haralens.recommendations import RecommendationEngine, RecommendationResult
from haralens.scoring import HealthScorer, HealthScoreResult
from haralens.semantic import DatasetSemanticProfile, infer_semantic_types


@dataclass(frozen=True, slots=True)
class AnalysisResult:
    """Complete session-scoped result; raw bytes are never retained."""

    upload_identity: str
    source_name: str
    ingestion: IngestionResult
    semantic: DatasetSemanticProfile
    profile: DatasetProfile
    quality: QualityRunResult
    health: HealthScoreResult
    recommendations: RecommendationResult
    analytics: AnalyticsResult
    readiness: AIReadinessResult
    insights: InsightResult


def analyze_uploaded_dataset(
    content: bytes,
    filename: str,
    *,
    worksheet_name: str | None = None,
    settings: Settings | None = None,
) -> AnalysisResult:
    """Run ingestion through recommendations exactly once for one upload."""

    effective_settings = settings or Settings()
    source_type = _source_type(filename)
    request = IngestionRequest(
        content=content,
        source_name=filename,
        limits=effective_settings.ingestion_limits,
        worksheet_name=worksheet_name,
    )
    ingestion = _adapter(source_type).ingest(request)
    semantic = infer_semantic_types(ingestion)
    profile = profile_dataset(ingestion, semantic)
    context = QualityCheckContext(
        table=ingestion.table,
        semantic_profile=semantic,
        dataset_profile=profile,
        ingestion_metadata=ingestion.metadata,
    )
    quality = QualityCheckRunner().run(
        context,
        create_default_quality_registry(),
        QualityFrameworkConfig(),
    )
    health = HealthScoreResult.model_validate(HealthScorer().score(quality).model_dump())
    recommendations = RecommendationEngine().generate(quality, health)
    analytics = analyze_frame(ingestion.table, profile, semantic)
    readiness = assess_readiness(ingestion.table, semantic, profile, analytics)
    insights = generate_insights(quality, readiness, analytics)
    return AnalysisResult(
        upload_identity=hashlib.sha256(content).hexdigest(),
        source_name=ingestion.metadata.source_name,
        ingestion=ingestion,
        semantic=semantic,
        profile=profile,
        quality=quality,
        health=health,
        recommendations=recommendations,
        analytics=analytics,
        readiness=readiness,
        insights=insights,
    )


def _source_type(filename: str) -> SourceType:
    suffix = PurePath(filename).suffix.casefold()
    if suffix == ".csv":
        return SourceType.CSV
    if suffix == ".xlsx":
        return SourceType.XLSX
    if suffix == ".parquet":
        return SourceType.PARQUET
    raise ValueError("HaraLens supports CSV, XLSX, and Parquet files.")


def _adapter(source_type: SourceType) -> IngestionAdapter:
    adapter_type = {
        SourceType.CSV: CsvIngestionAdapter,
        SourceType.XLSX: XlsxIngestionAdapter,
        SourceType.PARQUET: ParquetIngestionAdapter,
    }[source_type]
    return cast(IngestionAdapter, adapter_type())
