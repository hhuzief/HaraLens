"""Typed, safe failures for profiling input and resource contracts."""

from enum import StrEnum


class ProfilingErrorCode(StrEnum):
    INPUT_SHAPE_MISMATCH = "INPUT_SHAPE_MISMATCH"
    SEMANTIC_PROFILE_MISMATCH = "SEMANTIC_PROFILE_MISMATCH"
    RESOURCE_LIMIT_EXCEEDED = "RESOURCE_LIMIT_EXCEEDED"


class ProfilingError(ValueError):
    """A caller-safe profiling failure without raw data or exception details."""

    def __init__(
        self,
        code: ProfilingErrorCode,
        message: str,
        *,
        column_position: int | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.column_position = column_position

    def __str__(self) -> str:
        return self.message
