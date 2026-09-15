"""Small format-neutral safety helpers used by ingestion adapters."""

from collections import Counter
from collections.abc import Sequence

import pandas as pd

from haralens.ingestion.errors import (
    DuplicateColumnsError,
    IngestionConsistencyError,
    InvalidColumnNamesError,
    SourceTooLargeError,
)


def safe_display_name(value: str, *, fallback: str) -> str:
    """Reduce an untrusted path-like value to bounded display-only metadata."""
    basename = value.replace("\\", "/").rsplit("/", 1)[-1]
    printable = "".join(character if character.isprintable() else "_" for character in basename)
    return (printable or fallback)[:255]


def enforce_source_size(content: bytes, *, maximum: int) -> None:
    if len(content) > maximum:
        raise SourceTooLargeError(actual_bytes=len(content), max_bytes=maximum)


def validate_text_columns(columns: Sequence[object]) -> list[str]:
    invalid_positions = tuple(
        position
        for position, name in enumerate(columns, start=1)
        if not isinstance(name, str) or not name.strip()
    )
    if invalid_positions:
        raise InvalidColumnNamesError(column_positions=invalid_positions)

    names = [name for name in columns if isinstance(name, str)]
    counts = Counter(names)
    duplicates = tuple(dict.fromkeys(name for name in names if counts[name] > 1))
    if duplicates:
        raise DuplicateColumnsError(duplicate_columns=duplicates)
    return names


def enforce_materialization_invariant(
    table: pd.DataFrame,
    *,
    expected_rows: int,
    expected_columns: Sequence[str],
) -> None:
    actual_rows, actual_columns = table.shape
    if (
        actual_rows != expected_rows
        or actual_columns != len(expected_columns)
        or list(table.columns) != list(expected_columns)
    ):
        raise IngestionConsistencyError(
            expected_rows=expected_rows,
            actual_rows=actual_rows,
            expected_columns=len(expected_columns),
            actual_columns=actual_columns,
        )
