"""Validated process configuration; no external services required."""

from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

from haralens.ingestion.models import ResourceLimits


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="HARALENS_", env_file=".env", env_file_encoding="utf-8", extra="ignore"
    )

    environment: Literal["development", "test", "production"] = "development"
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "INFO"
    ingestion_max_source_bytes: int = Field(default=10 * 1024 * 1024, gt=0)
    ingestion_max_rows: int = Field(default=100_000, gt=0)
    ingestion_max_columns: int = Field(default=1_000, gt=0)

    @property
    def ingestion_limits(self) -> ResourceLimits:
        return ResourceLimits(
            max_source_bytes=self.ingestion_max_source_bytes,
            max_rows=self.ingestion_max_rows,
            max_columns=self.ingestion_max_columns,
        )
