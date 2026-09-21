"""Chart preparation only: never replace or recalculate official analytical scores.

Distribution aggregation and grouped quantiles describe observed values, not new
quality scores. All selection and sampling is deterministic and session independent.
"""

from __future__ import annotations

import math
from collections import Counter
from dataclasses import dataclass
from typing import Literal

import pandas as pd

from haralens.application import AnalysisResult
from haralens.quality.models import QualityDimension, QualityFinding

HEAT_ROWS = 60
HEAT_COLUMNS = 20
SCATTER_POINTS = 400
CATEGORIES = 10
ISSUE_COLUMNS = 20
HISTOGRAM_BINS = 24
ACTION_LINKS = 100
SEVERITY = {"informational": 0, "low": 1, "medium": 2, "high": 3, "critical": 4}
PRIORITY = {"urgent": 0, "high": 1, "medium": 2, "low": 3}
DIMENSIONS = tuple(item.value for item in QualityDimension)


@dataclass(frozen=True)
class Mark:
    label: str
    value: float | None
    detail: str = ""
    group: str = ""
    # Histogram edges, scatter y, or box (lower whisker, Q1, median, Q3, upper).
    coordinates: tuple[float, ...] = ()


@dataclass(frozen=True)
class Chart:
    title: str
    kind: Literal["bar", "donut", "radar", "heatmap", "histogram", "box", "scatter", "ring"]
    marks: tuple[Mark, ...] = ()
    caption: str = ""
    x_label: str = ""
    y_label: str = ""
    maximum: float | None = None
    empty: str = "No applicable observations are available."
    accent: Literal["health", "readiness", "neutral"] = "neutral"


def positions(total: int, limit: int) -> tuple[int, ...]:
    """Evenly spaced row positions including endpoints; no random state."""
    if limit < 1:
        raise ValueError("Sampling limit must be positive")
    if limit == 1:
        return (0,) if total else ()
    if total <= limit:
        return tuple(range(total))
    return tuple(i * (total - 1) // (limit - 1) for i in range(limit))


def findings(result: AnalysisResult) -> tuple[QualityFinding, ...]:
    return tuple(f for execution in result.quality.executions for f in execution.findings)


def scopes(finding: QualityFinding) -> tuple[str, ...]:
    return (
        (finding.target.column_name,)
        if finding.target.column_name is not None
        else finding.target.column_names
    )


def numeric_names(result: AnalysisResult) -> list[str]:
    return [
        c.column_name
        for c in result.profile.columns
        if c.statistics and c.statistics.kind == "numeric"
    ]


def categorical_names(result: AnalysisResult) -> list[str]:
    return [
        c.column_name
        for c in result.profile.columns
        if c.statistics and c.statistics.kind == "categorical"
    ]


def finite(series: pd.Series) -> pd.Series:
    values = pd.to_numeric(series, errors="coerce")
    return values[values.notna() & values.abs().lt(float("inf"))].astype(float)


def health(result: AnalysisResult) -> Chart:
    status = result.health.interpretation
    return Chart(
        "Data Health",
        "donut",
        (
            Mark(
                "Data Health",
                result.health.overall_score,
                status.value.replace("_", " ").title() if status else "Not evaluated",
            ),
        ),
        "Official Data Health Score · quality methodology",
        maximum=100,
        accent="health",
    )


def readiness(result: AnalysisResult) -> Chart:
    return Chart(
        "AI / ML Readiness",
        "donut",
        (
            Mark(
                "Readiness",
                result.readiness.overall_score,
                result.readiness.band.value.replace("_", " ").title(),
            ),
        ),
        "Technical preparation signal; not a model-performance prediction.",
        maximum=100,
        accent="readiness",
    )


def quality_dimensions(result: AnalysisResult) -> Chart:
    by_name = {d.dimension.value: d for d in result.health.dimensions}
    return Chart(
        "Quality dimension scores",
        "bar",
        tuple(
            Mark(
                name.replace("_", " ").title(),
                by_name[name].score,
                by_name[name].state.value.replace("_", " ").title(),
            )
            for name in DIMENSIONS
            if name in by_name
        ),
        "Official scores. Not evaluated is unavailable, never zero or perfect.",
        x_label="Score / 100",
        maximum=100,
    )


def readiness_dimensions(result: AnalysisResult) -> Chart:
    dims = result.readiness.dimensions
    return Chart(
        "Readiness dimensions",
        "radar" if len(dims) >= 3 else "bar",
        tuple(Mark(d.name.replace("_", " ").title(), d.score, d.measurement) for d in dims),
        "Calculated readiness dimensions only · common 0–100 scale.",
        maximum=100,
        accent="readiness",
    )


def missingness(result: AnalysisResult) -> Chart:
    columns = sorted(
        result.profile.columns, key=lambda c: (-c.missing_percentage, c.column_position)
    )[:HEAT_COLUMNS]
    rows = positions(len(result.ingestion.table), HEAT_ROWS)
    frame = result.ingestion.table.iloc[list(rows), [c.column_position for c in columns]].isna()
    return Chart(
        "Missingness heatmap",
        "heatmap",
        tuple(
            Mark(
                c.column_name,
                float(bool(frame.iloc[i, j])),
                "Missing" if frame.iloc[i, j] else "Present",
                f"Row {row + 1}",
            )
            for i, row in enumerate(rows)
            for j, c in enumerate(columns)
        ),
        f"{len(rows)} of {len(result.ingestion.table):,} rows, evenly spaced by original position; "
        f"{len(columns)} of {len(result.profile.columns)} columns, highest missingness first. "
        "M = missing; dot = present. No cell values are included.",
        x_label="Columns",
        y_label="Original row position",
        maximum=1,
    )


def ranked_columns(result: AnalysisResult) -> list[tuple[str, list[QualityFinding]]]:
    grouped: dict[str, list[QualityFinding]] = {}
    for finding in findings(result):
        for column in scopes(finding):
            grouped.setdefault(column, []).append(finding)
    return sorted(
        grouped.items(),
        key=lambda pair: (
            -max(SEVERITY[f.severity.value] for f in pair[1]),
            -len(pair[1]),
            pair[0],
        ),
    )


def issue_matrix(result: AnalysisResult) -> Chart:
    ranked = ranked_columns(result)
    marks: list[Mark] = []
    for column, items in ranked[:ISSUE_COLUMNS]:
        for dimension in DIMENSIONS:
            relevant = [f for f in items if f.dimension.value == dimension]
            severity = max((SEVERITY[f.severity.value] for f in relevant), default=0)
            label = next((name for name, value in SEVERITY.items() if value == severity), "none")
            marks.append(
                Mark(
                    dimension.replace("_", " ").title(),
                    float(severity),
                    f"{len(relevant)} findings; {label}" if relevant else "No finding",
                    column,
                )
            )
    dataset_count = sum(not scopes(f) for f in findings(result))
    return Chart(
        "Quality issue matrix",
        "heatmap",
        tuple(marks),
        f"Showing {min(len(ranked), ISSUE_COLUMNS)} of {len(ranked)} affected columns. "
        "Rank: highest severity, then finding count, then column name. "
        f"{dataset_count} dataset-wide findings remain in the findings list. "
        "L/M/H/C = low/medium/high/critical; dot = no finding (not proof of validity).",
        maximum=4,
    )


def histogram(result: AnalysisResult, column: str, *, title: str = "Distribution") -> Chart:
    values = finite(result.ingestion.table[column])
    missing = int(result.ingestion.table[column].isna().sum())
    if values.empty:
        return Chart(title, "histogram", empty="No finite numeric observations are available.")
    # Scale first to avoid overflow with finite values near floating-point limits.
    scale = max(float(values.abs().max()), 1.0)
    normalized = values / scale
    low, high = float(normalized.min()), float(normalized.max())
    bins = min(HISTOGRAM_BINS, max(1, math.ceil(math.sqrt(len(values))))) if low != high else 1
    width = (high - low) / bins
    if not width and low != high:
        bins, width = 1, high - low
    counts = [0] * bins
    for value in normalized:
        index = min(bins - 1, int((value - low) / width)) if width else 0
        counts[index] += 1
    marks = tuple(
        Mark(
            str(i + 1),
            float(count),
            coordinates=((low + i * width) * scale, min(high, low + (i + 1) * width) * scale),
        )
        for i, count in enumerate(counts)
    )
    excluded = len(result.ingestion.table) - len(values) - missing
    return Chart(
        title,
        "histogram",
        marks,
        f"{len(values):,} finite observations; {missing:,} missing and {excluded:,} non-finite/non-numeric excluded. "
        f"{bins} deterministic equal-width bins (up to {HISTOGRAM_BINS}).",
        x_label=column,
        y_label="Count",
    )


def _categories(series: pd.Series) -> list[tuple[object, int]]:
    counts = series.dropna().value_counts(sort=False)
    return sorted(
        ((value, int(count)) for value, count in counts.items()),
        key=lambda pair: (-pair[1], type(pair[0]).__name__, str(pair[0])),
    )


def frequency(
    result: AnalysisResult,
    column: str,
    *,
    anonymize: bool = False,
    title: str = "Category frequencies",
) -> Chart:
    series = result.ingestion.table[column]
    counts = _categories(series)
    total = int(series.notna().sum())
    marks = [
        Mark(
            f"Category {i + 1}" if anonymize else str(value),
            float(count),
            f"{100 * count / total:.1f}% of non-missing observations",
        )
        for i, (value, count) in enumerate(counts[:CATEGORIES])
    ]
    other = sum(count for _, count in counts[CATEGORIES:])
    if other:
        marks.append(
            Mark("Other (remaining categories)", float(other), f"{100 * other / total:.1f}%")
        )
    return Chart(
        title,
        "bar",
        tuple(marks),
        f"{column} · top {min(CATEGORIES, len(counts))} of {len(counts)} categories + Other when needed; "
        f"{int(series.isna().sum())} missing excluded. Counts are exact."
        + (" Category labels anonymized in export." if anonymize else ""),
        x_label="Count",
    )


def missing_present(result: AnalysisResult, column: str) -> Chart:
    profile = next(c for c in result.profile.columns if c.column_name == column)
    return Chart(
        "Missing vs present",
        "bar",
        (
            Mark(
                "Present", float(profile.non_null_count), f"{100 - profile.missing_percentage:.1f}%"
            ),
            Mark("Missing", float(profile.null_count), f"{profile.missing_percentage:.1f}%"),
        ),
        f"{profile.total_count:,} observations · exact profile counts.",
        x_label="Count",
    )


def box(result: AnalysisResult, column: str, *, target: str | None = None) -> Chart:
    if column not in numeric_names(result):
        return Chart(
            "Potential outliers",
            "box",
            empty="Not applicable: select a numeric column with computed quartiles.",
        )
    values = finite(result.ingestion.table[column])
    marks: list[Mark] = []
    if target is None:
        profile = next(c for c in result.profile.columns if c.column_name == column)
        stats = profile.statistics
        diagnostic = next((n for n in result.analytics.numeric if n.column_name == column), None)
        if stats and stats.kind == "numeric" and diagnostic:
            q = (
                diagnostic.lower_bound,
                stats.first_quartile,
                stats.median,
                stats.third_quartile,
                diagnostic.upper_bound,
            )
            if all(v is not None and math.isfinite(v) for v in q) and not values.empty:
                lower, q1, median, q3, upper = (float(v) for v in q if v is not None)
                inside = values[values.between(lower, upper)]
                if not inside.empty:
                    marks.append(
                        Mark(
                            column,
                            float(diagnostic.outlier_count),
                            f"{diagnostic.outlier_count} potential IQR outliers ({diagnostic.outlier_percentage:.1f}%)",
                            coordinates=(float(inside.min()), q1, median, q3, float(inside.max())),
                        )
                    )
    else:
        for value, _ in _categories(result.ingestion.table[target])[:CATEGORIES]:
            group = values[result.ingestion.table.loc[values.index, target].eq(value)]
            if group.empty:
                continue
            q1, median, q3 = (
                float(
                    group.quantile(
                        p, interpolation=result.profile.configuration.quantile_interpolation
                    )
                )
                for p in (0.25, 0.5, 0.75)
            )
            lower, upper = q1 - 1.5 * (q3 - q1), q3 + 1.5 * (q3 - q1)
            inside = group[group.between(lower, upper)]
            if not inside.empty and all(math.isfinite(v) for v in (lower, q1, median, q3, upper)):
                outliers = len(group) - len(inside)
                marks.append(
                    Mark(
                        str(value),
                        float(outliers),
                        f"n={len(group)}; {outliers} potential IQR outliers",
                        coordinates=(float(inside.min()), q1, median, q3, float(inside.max())),
                    )
                )
    return Chart(
        "Feature by target class" if target else "Potential outliers",
        "box",
        tuple(marks),
        (
            f"Top {CATEGORIES} target classes by frequency; missing targets excluded. Group quartiles are descriptive, not quality scores. "
            if target
            else "Uses canonical quartiles and IQR diagnostics. "
        )
        + "Box = Q1–Q3, line = median; whiskers = observed values inside 1.5 IQR. Outliers shown as counts, not raw records; they are not necessarily errors.",
        x_label=column,
        empty="No finite quartiles/whiskers are available.",
    )


def scatter(result: AnalysisResult, x: str, y: str, *, target: str | None = None) -> Chart:
    if x == y or x not in numeric_names(result) or y not in numeric_names(result):
        return Chart(
            "Feature relationship", "scatter", empty="Two distinct numeric variables are required."
        )
    frame = result.ingestion.table[[x, y]].apply(pd.to_numeric, errors="coerce")
    frame = frame.replace([float("inf"), float("-inf")], float("nan")).dropna()
    if target:
        classes = [value for value, _ in _categories(result.ingestion.table[target])[:CATEGORIES]]
        frame = frame[result.ingestion.table.loc[frame.index, target].isin(classes)]
    sampled = frame.iloc[list(positions(len(frame), SCATTER_POINTS))]
    class_order = _categories(result.ingestion.table[target])[:CATEGORIES] if target else []
    marks = tuple(
        Mark(
            "Observation",
            float(row.iloc[0]),
            group=(
                f"Class {next(i + 1 for i, (value, _) in enumerate(class_order) if value == result.ingestion.table.loc[index, target])}"
                if target
                else ""
            ),
            coordinates=(float(row.iloc[1]),),
        )
        for index, row in sampled.iterrows()
    )
    pair = next((p for p in result.analytics.correlations if {p.left, p.right} == {x, y}), None)
    correlation = (
        f" Canonical Pearson r={pair.coefficient:.3f}, n={pair.observation_count}."
        if pair and not target
        else ""
    )
    return Chart(
        "Feature vs target" if not target else "Features by target class",
        "scatter",
        marks,
        f"{len(sampled)} of {len(frame):,} eligible finite pairs, evenly spaced by row position."
        + (
            f" Top {CATEGORIES} target classes only; classes numbered by frequency, matching target distribution order."
            if target
            else ""
        )
        + correlation
        + " Association does not imply causation.",
        x_label=x,
        y_label=y,
    )


def column_quality(result: AnalysisResult, column: str) -> Chart:
    related = [f for f in findings(result) if column in scopes(f)]
    return Chart(
        "Column quality findings",
        "bar",
        tuple(
            Mark(d.replace("_", " ").title(), float(sum(f.dimension.value == d for f in related)))
            for d in DIMENSIONS
        ),
        "Finding counts, not column-level scores. Zero means no finding, not that every check was applicable.",
        x_label="Findings",
    )


def recommendation_dimensions(result: AnalysisResult) -> Chart:
    counts = Counter(r.dimension for r in result.recommendations.recommendations)
    return Chart(
        "Recommendations by dimension",
        "bar",
        tuple(Mark(d.replace("_", " ").title(), float(counts[d])) for d in DIMENSIONS),
        "Exact counts from recommendation provenance.",
        x_label="Recommendations",
    )


def affected_columns(result: AnalysisResult) -> Chart:
    linked_ids = {
        fid for r in result.recommendations.recommendations for fid in r.source_finding_ids
    }
    ranked = [
        (column, [f for f in items if f.finding_id in linked_ids])
        for column, items in ranked_columns(result)
    ]
    ranked = [(column, items) for column, items in ranked if items]
    ranked.sort(
        key=lambda pair: (-max(SEVERITY[f.severity.value] for f in pair[1]), -len(pair[1]), pair[0])
    )
    return Chart(
        "Affected columns",
        "bar",
        tuple(
            Mark(
                column,
                float(len(items)),
                f"Highest severity: {max(items, key=lambda f: SEVERITY[f.severity.value]).severity.value}",
            )
            for column, items in ranked[:ISSUE_COLUMNS]
        ),
        f"Top {min(len(ranked), ISSUE_COLUMNS)} of {len(ranked)} columns with actionable findings. "
        "Ranked by maximum severity, then linked finding count, then name; not a universal quality score.",
        x_label="Linked findings",
    )


def action_links(result: AnalysisResult) -> tuple[list[dict[str, str | float | None]], int]:
    by_id = {f.finding_id: f for f in findings(result)}
    rows: list[dict[str, str | float | None]] = []
    total = 0
    for recommendation in result.recommendations.recommendations:
        for fid in recommendation.source_finding_ids:
            total += 1
            if len(rows) >= ACTION_LINKS:
                continue
            finding = by_id.get(fid)
            rows.append(
                {
                    "Issue": finding.message if finding else "Source finding unavailable",
                    "Action": recommendation.message,
                    "Priority": recommendation.priority.value,
                    "Scope": ", ".join(scopes(finding))
                    if finding and scopes(finding)
                    else "Dataset",
                    "Finding ID": fid,
                    "Recommendation ID": recommendation.recommendation_id,
                    "Affected %": finding.affected_population.affected_percentage
                    if finding and finding.affected_population
                    else None,
                }
            )
    return rows, total


def remediation(result: AnalysisResult) -> Chart:
    recommendations = sorted(
        result.recommendations.recommendations,
        key=lambda r: (PRIORITY[r.priority.value], r.recommendation_id),
    )
    return Chart(
        "Remediation priority · evidence coverage",
        "bar",
        tuple(
            Mark(
                f"{r.priority.value.title()} · {r.title}",
                float(len(set(r.source_finding_ids))),
                f"{r.target_column or 'Dataset'}; {r.dimension}; recommendation {r.recommendation_id}",
            )
            for r in recommendations[:ISSUE_COLUMNS]
        ),
        f"Top {min(len(recommendations), ISSUE_COLUMNS)} of {len(recommendations)} recommendations, ordered by official priority then ID. "
        "Bar = distinct source findings linked to each action. Findings may overlap across actions. "
        "Evidence coverage is not predicted score improvement.",
        x_label="Linked findings",
    )


def report_charts(result: AnalysisResult) -> tuple[Chart, ...]:
    charts = [
        health(result),
        quality_dimensions(result),
        missingness(result),
        issue_matrix(result),
        readiness(result),
        readiness_dimensions(result),
    ]
    numeric = numeric_names(result)
    if numeric:
        charts.append(histogram(result, numeric[0], title="Selected numeric distribution"))
    if result.analytics.correlations:
        pairs = sorted(
            result.analytics.correlations, key=lambda p: (-abs(p.coefficient), p.left, p.right)
        )[:10]
        charts.append(
            Chart(
                "Strongest available correlations",
                "bar",
                tuple(
                    Mark(
                        f"{p.left} / {p.right}",
                        abs(p.coefficient),
                        f"Pearson r={p.coefficient:.3f}; n={p.observation_count}",
                    )
                    for p in pairs
                ),
                "Up to 10 canonical pairs by absolute correlation; signed r in labels. Association is not causation.",
                maximum=1,
                x_label="Absolute Pearson correlation",
            )
        )
    target = result.readiness.target
    if target:
        charts.append(
            histogram(result, target.target_name, title="Target distribution")
            if target.target_kind == "regression_candidate"
            else frequency(result, target.target_name, anonymize=True, title="Target distribution")
        )
    charts.extend((recommendation_dimensions(result), remediation(result)))
    return tuple(charts)


def overview_summaries(result: AnalysisResult) -> tuple[Chart, Chart, Chart, Chart]:
    dimensions = quality_dimensions(result)
    if len(dimensions.marks) >= 3 and all(m.value is not None for m in dimensions.marks):
        from dataclasses import replace

        dimensions = replace(dimensions, kind="radar", title="Quality dimensions")
    counts = Counter(f.severity.value for f in findings(result))
    severity = Chart(
        "Issues by severity",
        "bar",
        tuple(
            Mark(label.title(), float(counts[label]), group=color)
            for label, color in (
                ("critical", "critical"),
                ("high", "warning"),
                ("medium", "medium"),
                ("low", "health"),
            )
        ),
        "Counts of canonical findings by severity.",
        x_label="Findings",
    )
    semantics = Chart(
        "Semantic type distribution",
        "ring",
        tuple(
            Mark(item.semantic_type.value.replace("_", " ").title(), float(item.count))
            for item in result.semantic.semantic_type_counts
        ),
        "Exact inferred semantic types across all columns.",
        x_label="columns",
    )
    columns = sorted(
        result.profile.columns, key=lambda c: (-c.missing_percentage, c.column_position)
    )[:5]
    missing = Chart(
        "Top columns by missingness",
        "bar",
        tuple(
            Mark(
                c.column_name,
                c.missing_percentage,
                f"{c.null_count:,} missing",
                group="critical" if c.missing_percentage else "health",
            )
            for c in columns
        ),
        f"Top {len(columns)} of {len(result.profile.columns)} columns; exact profile percentages.",
        x_label="Missing %",
        maximum=100,
    )
    return dimensions, severity, semantics, missing
