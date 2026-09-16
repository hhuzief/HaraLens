"""Representative bounded profiling checks without flaky timing assertions."""

import pandas as pd

from haralens.profiling import NumericStatistics, profile_dataset
from haralens.semantic import infer_semantic_types


def test_exact_profile_on_100k_representative_rows() -> None:
    rows = 100_000
    table = pd.DataFrame(
        {
            "amount": [float(index % 10_000) / 10 for index in range(rows)],
            "region": [f"region-{index % 12}" for index in range(rows)],
            "is_active": [index % 2 == 0 for index in range(rows)],
        }
    )
    semantic = infer_semantic_types(table)

    profile = profile_dataset(table, semantic)

    assert profile.summary.row_count == rows
    assert profile.summary.column_count == 3
    assert profile.summary.duplicate_row_count == 70_000
    assert profile.run_metadata.exact is True
    statistics = profile.columns[0].statistics
    assert isinstance(statistics, NumericStatistics)
    assert statistics.finite_count == rows
