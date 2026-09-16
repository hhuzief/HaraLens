"""Validated, immutable policy for deterministic dataset profiling."""

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class ProfilingConfig(BaseModel):
    """Resource and presentation bounds for exact profiling.

    The service never samples. Inputs beyond these bounds fail explicitly so a direct
    ``DataFrame`` caller cannot accidentally request unbounded work.
    """

    model_config = ConfigDict(frozen=True, extra="forbid", strict=True, allow_inf_nan=False)

    max_rows: int = Field(default=100_000, gt=0)
    max_columns: int = Field(default=1_000, gt=0)
    max_cells: int = Field(default=10_000_000, gt=0)
    top_values_limit: int = Field(default=10, ge=1, le=100)
    max_value_display_length: int = Field(default=200, ge=16, le=4_096)
    standard_deviation_ddof: Literal[0, 1] = 1
    quantile_interpolation: Literal["linear", "lower", "higher", "midpoint", "nearest"] = "linear"
