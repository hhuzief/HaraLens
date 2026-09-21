"""HaraLens v0.1 Streamlit product workflow."""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from haralens import __version__
from haralens.application import AnalysisResult, analyze_uploaded_dataset
from haralens.ingestion import IngestionError, WorksheetSelectionRequiredError
from haralens.quality import Severity
from haralens.reporting import build_html_report, safe_report_filename
from haralens.visualization import dashboard, prepare
from haralens.visualization.theme import page_header

st.set_page_config(page_title="HaraLens", page_icon="◈", layout="wide")


def _state() -> None:
    defaults: dict[str, Any] = {
        "analysis_result": None,
        "upload_identity": None,
        "source_name": None,
        "worksheet_name": None,
        "worksheet_options": (),
        "analysis_error": None,
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def home() -> None:
    st.title("HaraLens")
    st.subheader("Know your data before you trust it.")
    st.write(
        "HaraLens analyzes tabular data for structure, quality, analytical readiness, and explainable next steps before you rely on it."
    )
    st.info("Phase 0 foundation · Gate 1 intelligence integrated.")
    first, second, third = st.columns(3)
    first.markdown(
        "**Data profiling**\n\nUnderstand rows, columns, missingness, and semantic types."
    )
    second.markdown(
        "**Quality diagnostics**\n\nInspect deterministic findings across six dimensions."
    )
    third.markdown(
        "**Explainable guidance**\n\nSee how the score is built and what to investigate next."
    )
    st.markdown("### Supported formats")
    st.write("CSV · XLSX · Parquet")
    st.caption(
        "Uploads are processed by the HaraLens server for the current analysis and are not intentionally saved to an application database. Results are session-scoped; upload only data you are authorized to process."
    )
    st.caption(f"HaraLens v{__version__} · Deterministic configured quality methodology")


def analyze() -> None:
    _state()
    st.title("Analyze a dataset")
    st.write("Upload a supported tabular file to build a session-scoped HaraLens analysis.")
    st.caption(
        "Limits: 10 MiB · 100,000 rows · 1,000 columns. Excel and Parquet have additional structural limits."
    )
    uploaded = st.file_uploader(
        "Choose a CSV, XLSX, or Parquet file", type=["csv", "xlsx", "parquet"]
    )
    if uploaded is not None:
        st.caption(f"Selected: {uploaded.name} · {uploaded.size:,} bytes")
    if st.session_state.analysis_result is not None:
        if st.button("Analyze another dataset", type="secondary"):
            _reset()
            st.rerun()
        result = st.session_state.analysis_result
        st.success(f"Analysis complete for {result.source_name}. Use the sidebar to view results.")
        st.write(
            f"{result.profile.summary.row_count:,} rows · "
            f"{result.profile.summary.column_count:,} columns · "
            f"Health {result.health.overall_score if result.health.overall_score is not None else 'not evaluated'} · "
            f"AI readiness {result.readiness.overall_score:.1f}"
        )
        return
    if uploaded is None:
        st.info("Choose a file to begin. No dataset is displayed automatically.")
        return
    options = st.session_state.get("worksheet_options", ())
    worksheet = st.selectbox("Choose a worksheet", options) if options else None
    if st.button("Start analysis", type="primary"):
        _run_analysis(uploaded, worksheet)
    if st.session_state.analysis_error:
        _render_error(st.session_state.analysis_error)


def methodology() -> None:
    st.title("Methodology")
    st.write(
        "HaraLens evaluates a dataset against a deterministic configured quality methodology. The result supports investigation; it is not a universal cleanliness or ML-readiness guarantee."
    )
    st.markdown("### Six dimensions")
    st.write(
        "Completeness · Uniqueness · Validity · Consistency · Integrity · Analytical readiness"
    )
    st.markdown("### Scores")
    st.write(
        "Scores use engine-produced findings, severity, affected prevalence, transparent dimension weights, and linked root-cause contributions. A dimension with no evaluated checks is shown as Not evaluated."
    )
    st.markdown("### Privacy and limits")
    st.write(
        "Uploads are session-scoped. HaraLens does not intentionally persist datasets in v0.1. Findings and recommendations omit raw cell values and category examples."
    )


def _run_analysis(uploaded: Any, worksheet: str | None) -> None:
    st.session_state.analysis_error = None
    try:
        with st.status("Analyzing dataset", expanded=True) as status:
            st.write("Validating and reading dataset...")
            st.write("Understanding column types...")
            st.write("Profiling dataset...")
            st.write("Running quality checks and calculating score...")
            result = analyze_uploaded_dataset(
                uploaded.getvalue(), uploaded.name, worksheet_name=worksheet
            )
            st.write("Preparing recommendations...")
            status.update(label="Analysis complete", state="complete", expanded=False)
    except WorksheetSelectionRequiredError as error:
        st.session_state.worksheet_options = error.available_worksheets
        st.session_state.analysis_error = error
        return
    except (IngestionError, ValueError, OSError) as error:
        st.session_state.analysis_error = error
        st.session_state.worksheet_options = ()
        return
    st.session_state.analysis_result = result
    st.session_state.upload_identity = result.upload_identity
    st.session_state.source_name = result.source_name
    st.session_state.worksheet_name = worksheet
    st.session_state.worksheet_options = ()
    st.rerun()


def _render_readiness(result: AnalysisResult) -> None:
    dashboard.readiness(result)


def _render_explore(result: AnalysisResult) -> None:
    page_header("Explore", "Inspect distributions, relationships, and missingness in your dataset.")
    distribution_tab, relationship_tab, missingness_tab = st.tabs(
        ["Distributions", "Relationships", "Missingness"]
    )
    numeric = result.analytics.numeric
    with distribution_tab, st.container(border=True):
        if not numeric:
            st.info("No eligible numeric columns are available for numerical exploration.")
        else:
            selected = st.selectbox(
                "Numeric column", [item.column_name for item in numeric], key="explore_numeric"
            )
            column = result.profile.columns[
                [item.column_name for item in result.profile.columns].index(selected)
            ]
            st.write(
                f"**{selected}** · {next(item.skewness_interpretation for item in numeric if item.column_name == selected)}"
            )
            dashboard.show(prepare.histogram(result, selected))
            values = (
                pd.to_numeric(result.ingestion.table[selected], errors="coerce").dropna().head(5000)
            )
            with st.expander("Values by observation"):
                st.caption("First 5,000 non-missing observations in source order.")
                st.bar_chart(values.reset_index(drop=True), height=240)
            if column.statistics and column.statistics.kind == "numeric":
                st.dataframe(
                    pd.DataFrame([column.statistics.model_dump()]),
                    use_container_width=True,
                    hide_index=True,
                )
        categories = prepare.categorical_names(result)
        if categories:
            category = st.selectbox("Categorical column", categories, key="visual_explore_category")
            dashboard.show(prepare.frequency(result, category))
    with relationship_tab, st.container(border=True):
        eligible = [item.column_name for item in numeric]
        if len(eligible) < 2:
            st.info(
                "At least two eligible numeric columns are required for relationship exploration."
            )
        else:
            left, right = st.columns(2)
            x = left.selectbox("X numeric variable", eligible, key="explore_relationship_x")
            y = right.selectbox(
                "Y numeric variable",
                [name for name in eligible if name != x],
                key="explore_relationship_y",
            )
            points = (
                result.ingestion.table[[x, y]]
                .apply(pd.to_numeric, errors="coerce")
                .replace([float("inf"), float("-inf")], pd.NA)
                .dropna()
                .head(5000)
            )
            st.scatter_chart(points, x=x, y=y, height=300)
            pair = next(
                (
                    item
                    for item in result.analytics.correlations
                    if {item.left, item.right} == {x, y}
                ),
                None,
            )
            st.caption(
                f"Pearson correlation: {pair.coefficient:.3f} across {pair.observation_count} observations."
                if pair
                else "Correlation is unavailable for this pair."
            )
            with st.expander("All computed correlations"):
                st.dataframe(
                    pd.DataFrame([item.model_dump() for item in result.analytics.correlations]),
                    use_container_width=True,
                    hide_index=True,
                )
    with missingness_tab, st.container(border=True):
        dashboard.show(prepare.missingness(result))
        st.dataframe(_missingness_rows(result).head(50), use_container_width=True, hide_index=True)


def _render_overview(result: AnalysisResult) -> None:
    page_header("Overview", "Executive summary of your dataset’s health and AI readiness.")
    active = dashboard.with_target(result, st.session_state.get("visual_selected_target"))
    dashboard.pair(prepare.health(result), prepare.readiness(active))
    dimensions, severity, semantics, missing = prepare.overview_summaries(result)
    dashboard.pair(dimensions, severity)
    dashboard.pair(semantics, missing)
    summary = result.profile.summary
    columns = st.columns(4)
    columns[0].metric("Rows", f"{summary.row_count:,}")
    columns[1].metric("Columns", f"{summary.column_count:,}")
    columns[2].metric("Missing cells", f"{summary.missing_cell_count:,}")
    columns[3].metric("Duplicate rows", f"{summary.duplicate_row_count or 0:,}")
    with st.expander("Profile details"):
        st.dataframe(_dimension_rows(result), use_container_width=True, hide_index=True)
        st.dataframe(_missingness_rows(result).head(25), use_container_width=True, hide_index=True)
        st.caption("Missingness details: up to 25 columns, highest missingness first.")


def _render_quality(result: AnalysisResult) -> None:
    page_header("Data Quality", "Detailed analysis of data quality issues and dimensions.")
    dashboard.quality(result)
    findings = [
        finding for execution in result.quality.executions for finding in execution.findings
    ]
    counts = {
        severity: sum(finding.severity is severity for finding in findings) for severity in Severity
    }
    cards = st.columns(4)
    for card, severity in zip(
        cards, (Severity.CRITICAL, Severity.HIGH, Severity.MEDIUM, Severity.LOW), strict=True
    ):
        card.metric(severity.value.title(), counts[severity])
    if not findings:
        st.success("No quality findings were generated under the configured HaraLens methodology.")
        return
    dimensions = sorted({finding.dimension.value for finding in findings})
    selected_dimension = st.selectbox("Filter by dimension", ["All", *dimensions])
    selected_severity = st.selectbox(
        "Filter by severity",
        ["All", *[severity.value for severity in Severity if counts[severity]]],
    )
    rows = []
    for finding in findings:
        if selected_dimension != "All" and finding.dimension.value != selected_dimension:
            continue
        if selected_severity != "All" and finding.severity.value != selected_severity:
            continue
        population = finding.affected_population
        rows.append(
            {
                "Issue": finding.message,
                "Severity": finding.severity.value,
                "Dimension": finding.dimension.value,
                "Target": finding.target.column_name or "Dataset",
                "Affected %": population.affected_percentage if population else None,
            }
        )
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    st.markdown("### Why this score?")
    for dimension in result.health.dimensions:
        for contribution in dimension.penalties:
            if contribution.applied:
                st.write(
                    f"{dimension.dimension.value.replace('_', ' ').title()}: −{contribution.penalty_points:.2f} points · {contribution.finding_family.replace('_', ' ')}"
                )


def _render_columns(result: AnalysisResult) -> None:
    page_header("Column Analysis", "Detailed analysis for each column in your dataset.")
    if not result.profile.columns:
        st.info("No columns are available for exploration.")
        return
    dashboard.column(result)
    selected = st.session_state.selected_column
    column = next(c for c in result.profile.columns if c.column_name == selected)
    with st.expander("Complete column profile"):
        st.write(f"Semantic inference confidence: {column.semantic_confidence.value}")
        st.json(column.model_dump(mode="json"))


def _render_recommendations(result: AnalysisResult) -> None:
    page_header("Recommendations", "Prioritized recommendations to improve your dataset.")
    dashboard.recommendations(result)
    recommendations = result.recommendations.recommendations
    if not recommendations:
        st.info(
            "No remediation recommendations were generated under the current HaraLens quality methodology."
        )
        return
    for priority in ("urgent", "high", "medium", "low"):
        group = [item for item in recommendations if item.priority.value == priority]
        if group:
            st.markdown(f"### {priority.title()}")
            for item in group:
                st.markdown(f"**{item.title}** · {item.target_column or 'dataset'}")
                st.write(item.message)


def _dimension_rows(result: AnalysisResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "dimension": item.dimension.value,
                "score": item.score,
                "state": item.state.value.replace("_", " ").title(),
            }
            for item in result.health.dimensions
        ]
    )


def _semantic_rows(result: AnalysisResult) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {"semantic_type": item.semantic_type.value, "count": item.count}
            for item in result.semantic.semantic_type_counts
        ]
    )


def _missingness_rows(result: AnalysisResult) -> pd.DataFrame:
    rows = [
        {
            "column": item.column_name,
            "missing": item.null_count,
            "missing_percentage": item.missing_percentage,
        }
        for item in result.profile.columns
    ]
    return pd.DataFrame(rows).sort_values(["missing_percentage", "column"], ascending=[False, True])


def _render_error(error: Exception) -> None:
    title = "Analysis could not be completed"
    message = getattr(error, "message", str(error))
    if isinstance(error, WorksheetSelectionRequiredError):
        title = "Choose a worksheet"
        message = "This workbook contains multiple usable worksheets. Select one to continue."
    st.error(f"**{title}**\n\n{message}")


def _reset() -> None:
    for key in list(st.session_state):
        if str(key).startswith("visual_"):
            st.session_state.pop(key, None)
    for key in (
        "analysis_result",
        "upload_identity",
        "source_name",
        "worksheet_name",
        "worksheet_options",
        "analysis_error",
        "readiness_target",
        "explore_numeric",
        "explore_relationship_x",
        "explore_relationship_y",
        "selected_column",
    ):
        st.session_state.pop(key, None)
    _state()


def _inactive_result_page() -> None:
    st.title("No active analysis")
    st.info("No active analysis. Analyze a dataset first.")
    st.write("Use **Analyze** in the sidebar to upload a CSV, XLSX, or Parquet dataset.")


def overview_page() -> None:
    result = st.session_state.get("analysis_result")
    if result is None:
        _inactive_result_page()
        return
    _render_overview(result)
    st.markdown("### Top insights")
    for insight in result.insights.insights[: result.insights.display_limit]:
        st.markdown(f"**{insight.title}** — {insight.message}")
    st.markdown("### Key risks")
    risks = result.readiness.blockers or result.readiness.warnings
    st.info("; ".join(risks) if risks else "No readiness blockers were identified.")


def data_quality_page() -> None:
    result = st.session_state.get("analysis_result")
    _render_quality(result) if result is not None else _inactive_result_page()


def readiness_page() -> None:
    result = st.session_state.get("analysis_result")
    _render_readiness(result) if result is not None else _inactive_result_page()


def explore_page() -> None:
    result = st.session_state.get("analysis_result")
    _render_explore(result) if result is not None else _inactive_result_page()


def columns_page() -> None:
    result = st.session_state.get("analysis_result")
    _render_columns(result) if result is not None else _inactive_result_page()


def recommendations_page() -> None:
    result = st.session_state.get("analysis_result")
    _render_recommendations(result) if result is not None else _inactive_result_page()


def report_page() -> None:
    result = st.session_state.get("analysis_result")
    if result is None:
        _inactive_result_page()
        return
    result = dashboard.with_target(
        result,
        st.session_state.get("visual_selected_target", st.session_state.get("readiness_target")),
    )
    report = build_html_report(result)
    page_header(
        "HaraLens Analysis Report", "Review the complete analysis before exporting your report."
    )
    st.caption(f"Dataset: {result.source_name} · HTML report · Session-scoped")
    st.markdown("### Report Preview")
    components.html(report, height=1100, scrolling=True)
    st.markdown("### Export Report")
    st.download_button(
        "Download HaraLens Report",
        data=report,
        file_name=safe_report_filename(result.source_name),
        mime="text/html",
        help="Download the same report shown in the preview.",
    )


def _build_pages(active_result: AnalysisResult | None) -> list[Any]:
    pages: list[Any] = [
        st.Page(home, title="Home", icon=":material/home:", default=active_result is None),
        st.Page(analyze, title="Analyze", icon=":material/upload_file:"),
    ]
    if active_result is not None:
        pages.extend(
            [
                st.Page(overview_page, title="Overview", icon=":material/dashboard:", default=True),
                st.Page(data_quality_page, title="Data Quality", icon=":material/fact_check:"),
                st.Page(readiness_page, title="AI Readiness", icon=":material/model_training:"),
                st.Page(explore_page, title="Explore", icon=":material/explore:"),
                st.Page(columns_page, title="Columns", icon=":material/view_column:"),
                st.Page(
                    recommendations_page,
                    title="Recommendations",
                    icon=":material/tips_and_updates:",
                ),
                st.Page(report_page, title="Report", icon=":material/description:"),
            ]
        )
    pages.append(st.Page(methodology, title="Methodology / About", icon=":material/info:"))
    return pages


st.logo(
    '<svg xmlns="http://www.w3.org/2000/svg" width="165" height="48" viewBox="0 0 165 48">'
    '<text x="0" y="24" fill="#f1f5f9" font-family="Arial,sans-serif" '
    'font-size="24" font-weight="700">HaraLens</text>'
    '<text x="0" y="44" fill="#b3c4d3" font-family="Arial,sans-serif" font-size="13">v0.1</text>'
    "</svg>",
    size="large",
)

_state()
active_result = st.session_state.get("analysis_result")
if active_result is not None:
    st.sidebar.markdown("### Current dataset")
    st.sidebar.caption(str(active_result.source_name))
    st.sidebar.caption(
        f"{active_result.profile.summary.row_count:,} rows · "
        f"{active_result.profile.summary.column_count:,} columns"
    )
st.navigation(_build_pages(active_result), position="sidebar").run()
