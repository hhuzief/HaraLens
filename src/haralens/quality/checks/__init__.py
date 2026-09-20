"""Explicit production quality-check catalogue for HaraLens v0.1."""

from haralens.quality.checks.catalogue import create_default_quality_registry
from haralens.quality.checks.config import ProductionQualityConfig

__all__ = ["ProductionQualityConfig", "create_default_quality_registry"]
