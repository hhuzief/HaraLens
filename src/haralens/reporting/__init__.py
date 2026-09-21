"""Safe, bounded HTML report generation for completed HaraLens analyses."""

import re
from html import escape
from pathlib import PurePath

from haralens.application import AnalysisResult
from haralens.reporting.styles import REPORT_CSS
from haralens.visualization.prepare import report_charts
from haralens.visualization.render import CHART_CSS, render_chart

MAX_COLUMN_DETAILS = 50
MAX_FINDINGS = 100
MAX_RECOMMENDATIONS = 100
MAX_CORRELATIONS = 20


def safe_report_filename(source_name: str) -> str:
    """Return a deterministic download name without path separators or traversal."""

    stem = PurePath(source_name.replace("\\", "/")).stem
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "dataset"
    return f"haralens_report_{safe}.html"


def _cell(value: object) -> str:
    return escape(str(value))


def _numeric_summary(column: object) -> str:
    statistics = getattr(column, "statistics", None)
    if statistics is None or getattr(statistics, "kind", None) != "numeric":
        return ""
    fields = (
        ("n", statistics.finite_count),
        ("mean", statistics.mean),
        ("median", statistics.median),
        ("sd", statistics.standard_deviation),
        ("min", statistics.minimum),
        ("max", statistics.maximum),
        ("Q1", statistics.first_quartile),
        ("Q3", statistics.third_quartile),
        ("IQR", statistics.interquartile_range),
        ("skew", statistics.skewness),
        ("kurtosis", statistics.kurtosis),
    )
    return "; ".join(f"{label}: {_cell(value)}" for label, value in fields if value is not None)


def build_html_report(result: AnalysisResult) -> str:
    """Build one bounded, self-contained HTML artifact from a completed analysis."""

    summary = result.profile.summary
    semantic_rows = (
        "".join(
            f"<tr><td>{_cell(item.semantic_type.value)}</td><td>{item.count:,}</td></tr>"
            for item in result.semantic.semantic_type_counts
        )
        or "<tr><td colspan='2'>No semantic types were inferred.</td></tr>"
    )
    health_rows = "".join(
        f"<tr><td>{_cell(item.dimension.value.replace('_', ' ').title())}</td>"
        f"<td>{item.score:.1f}</td><td>{_cell(item.state.value.replace('_', ' ').title())}</td></tr>"
        if item.score is not None
        else f"<tr><td>{_cell(item.dimension.value.replace('_', ' ').title())}</td>"
        f"<td>Not evaluated</td><td>{_cell(item.state.value.replace('_', ' ').title())}</td></tr>"
        for item in result.health.dimensions
    )
    findings = [
        finding for execution in result.quality.executions for finding in execution.findings
    ]
    finding_rows = (
        "".join(
            f"<tr><td>{_cell(finding.dimension.value.replace('_', ' ').title())}</td>"
            f"<td>{_cell(finding.severity.value.title())}</td>"
            f"<td>{_cell(finding.target.column_name or 'Dataset')}</td>"
            f"<td>{_cell(finding.message)}</td>"
            f"<td>{_cell(finding.affected_population.affected_percentage if finding.affected_population else 'n/a')}</td></tr>"
            for finding in findings[:MAX_FINDINGS]
        )
        or "<tr><td colspan='5'>No quality findings were generated.</td></tr>"
    )
    recommendation_rows = (
        "".join(
            f"<tr><td>{_cell(item.priority.value.title())}</td><td>{_cell(item.title)}</td>"
            f"<td>{_cell(item.dimension)}</td><td>{_cell(item.target_column or 'Dataset')}</td>"
            f"<td>{_cell(item.message)}</td></tr>"
            for item in result.recommendations.recommendations[:MAX_RECOMMENDATIONS]
        )
        or "<tr><td colspan='5'>No recommendations were generated.</td></tr>"
    )
    insights = (
        "".join(
            f"<li><strong>{_cell(item.title)}</strong>: {_cell(item.message)}</li>"
            for item in result.insights.insights[: result.insights.display_limit]
        )
        or "<li>No deterministic insights were generated.</li>"
    )
    column_profiles = result.profile.columns[:MAX_COLUMN_DETAILS]
    column_rows = (
        "".join(
            f"<tr><td>{_cell(column.column_name)}</td><td>{_cell(column.semantic_type.value)}</td>"
            f"<td>{_cell(column.physical_dtype)}</td><td>{column.null_count:,} ({column.missing_percentage:.1f}%)</td>"
            f"<td>{_cell(column.unique_count if column.unique_count is not None else 'n/a')}</td>"
            f"<td>{_numeric_summary(column)}</td></tr>"
            for column in column_profiles
        )
        or "<tr><td colspan='6'>No column profiles were generated.</td></tr>"
    )
    numeric_rows = (
        "".join(
            f"<tr><td>{_cell(item.column_name)}</td><td>{item.outlier_count:,}</td>"
            f"<td>{item.outlier_percentage:.1f}%</td><td>{_cell(item.skewness_interpretation)}</td></tr>"
            for item in result.analytics.numeric[:MAX_COLUMN_DETAILS]
        )
        or "<tr><td colspan='4'>No numerical diagnostics were generated.</td></tr>"
    )
    correlation_rows = (
        "".join(
            f"<tr><td>{_cell(item.left)}</td><td>{_cell(item.right)}</td>"
            f"<td>{item.coefficient:.3f}</td><td>{item.observation_count:,}</td></tr>"
            for item in result.analytics.correlations[:MAX_CORRELATIONS]
        )
        or "<tr><td colspan='4'>No bounded correlations were generated.</td></tr>"
    )
    missing_rows = (
        "".join(
            f"<tr><td>{_cell(column.column_name)}</td><td>{column.null_count:,}</td>"
            f"<td>{column.missing_percentage:.1f}%</td></tr>"
            for column in result.profile.columns
            if column.null_count
        )
        or "<tr><td colspan='3'>No missing values were observed.</td></tr>"
    )
    health_score = (
        f"{result.health.overall_score:.1f} / 100"
        if result.health.overall_score is not None
        else "Not evaluated"
    )
    omitted_columns = max(0, len(result.profile.columns) - len(column_profiles))
    omitted_findings = max(0, len(findings) - MAX_FINDINGS)
    omitted_recommendations = max(
        0, len(result.recommendations.recommendations) - MAX_RECOMMENDATIONS
    )
    readiness_rows = "".join(
        f"<tr><td>{_cell(item.name)}</td><td>{item.score:.1f}</td><td>{_cell(item.measurement)}</td></tr>"
        for item in result.readiness.dimensions
    )
    document = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width, initial-scale=1'>
<meta name='color-scheme' content='only light'><title>HaraLens report</title>
<style>{REPORT_CSS}
{CHART_CSS}</style></head>
<body><h1>HaraLens v0.1 report</h1><h2>Data Health &amp; AI Readiness Report</h2><p>Dataset: {_cell(result.source_name)}</p>
<p>Report methodology version: {_cell(result.profile.profile_version)} · Quality methodology: {_cell(result.quality.metadata.quality_framework_version)}</p>
<section><h2>Dataset overview</h2><p>Rows: {summary.row_count:,} · Columns: {summary.column_count:,} · Cells: {summary.cell_count:,} · Memory: {summary.memory_bytes:,} bytes · Missing cells: {summary.missing_cell_count:,} · Duplicate rows: {_cell(summary.duplicate_row_count if summary.duplicate_row_count is not None else "Unavailable")}</p><table><tr><th>Inferred semantic type</th><th>Columns</th></tr>{semantic_rows}</table></section>
<section><h2>Data Health</h2><p class='score'>{health_score}</p><p>Status: {_cell(result.health.interpretation.value.replace("_", " ").title()) if result.health.interpretation else "Not evaluated"}</p><table><tr><th>Dimension</th><th>Score</th><th>State</th></tr>{health_rows}</table><p class='note'>Scores are deterministic. “Not evaluated” means no applicable check was executed; it does not mean the dimension is perfect.</p></section>
<section><h2>Data-quality findings</h2><table><tr><th>Dimension</th><th>Severity</th><th>Scope</th><th>Finding</th><th>Affected %</th></tr>{finding_rows}</table>{f"<p class='note'>{omitted_findings} additional findings omitted by the report bound.</p>" if omitted_findings else ""}</section>
<section><h2>AI/ML Readiness</h2><p class='score'>{result.readiness.overall_score:.1f} / 100 ({_cell(result.readiness.band.value.replace("_", " ").title())})</p><table><tr><th>Dimension</th><th>Score</th><th>Measurement</th></tr>{readiness_rows}</table><p><strong>Blockers:</strong> {_cell("; ".join(result.readiness.blockers) or "None")}</p><p><strong>Warnings:</strong> {_cell("; ".join(result.readiness.warnings) or "None")}</p><p><strong>Strengths:</strong> {_cell("; ".join(result.readiness.strengths) or "None")}</p></section>
<section><h2>Missing data analysis</h2><table><tr><th>Column</th><th>Missing</th><th>Missing %</th></tr>{missing_rows}</table></section>
<section><h2>Statistical analysis</h2><table><tr><th>Column</th><th>Potential outliers</th><th>Outlier %</th><th>Interpretation</th></tr>{numeric_rows}</table></section>
<section><h2>Relationships</h2><table><tr><th>Left</th><th>Right</th><th>Pearson</th><th>Observations</th></tr>{correlation_rows}</table><p class='note'>Correlation does not imply causation.</p></section>
<section><h2>Column profiles</h2><table><tr><th>Column</th><th>Semantic type</th><th>Physical dtype</th><th>Missing</th><th>Distinct</th><th>Numeric summary</th></tr>{column_rows}</table>{f"<p class='note'>Detailed column profiles show the first {len(column_profiles)} columns from a dataset containing {len(result.profile.columns)} columns; {omitted_columns} columns omitted by the report bound.</p>" if omitted_columns else ""}</section>
<section><h2>Analytical insights</h2><ul>{insights}</ul></section>
<section><h2>Recommendations</h2><table><tr><th>Priority</th><th>Recommendation</th><th>Dimension</th><th>Scope</th><th>Detail</th></tr>{recommendation_rows}</table>{f"<p class='note'>{omitted_recommendations} additional recommendations omitted by the report bound.</p>" if omitted_recommendations else ""}</section>
<section><h2>Methodology and limitations</h2><p>HaraLens scores and observations are deterministic. AI Readiness is a readiness assessment, not a model-performance prediction. Correlation does not imply causation. Automated findings should be interpreted in dataset and business context. Target analysis is included only when a target is explicitly selected. HaraLens does not assess label validity, sampling bias, deployment representativeness, or causal validity.</p></section>
<section><h2>Visual analysis summary</h2>{"".join(render_chart(chart) for chart in report_charts(result))}</section>
</body></html>"""
    # Wrap only generated table markup; all user-controlled values are escaped above.
    return re.sub(
        r"<table><tr>(.*?)</tr>(.*?)</table>",
        r'<div class="table-scroll" role="region" aria-label="Report table" tabindex="0">'
        r"<table><thead><tr>\1</tr></thead><tbody>\2</tbody></table></div>",
        document,
        flags=re.DOTALL,
    )


__all__ = ["build_html_report", "safe_report_filename"]
