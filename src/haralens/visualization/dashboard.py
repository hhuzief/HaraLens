"""Streamlit composition; analytical preparation lives in frontend-neutral helpers."""

from dataclasses import replace

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components

from haralens.application import AnalysisResult
from haralens.readiness import assess_readiness

from . import prepare as p
from .render import chart_document
from .theme import page_header


def show(chart: p.Chart) -> None:
    components.html(
        chart_document(chart, dark=True),
        height=470 if chart.kind == "heatmap" else 375,
        scrolling=True,
    )


def pair(left: p.Chart, right: p.Chart) -> None:
    first, second = st.columns(2)
    with first:
        show(left)
    with second:
        show(right)


def quality(result: AnalysisResult) -> None:
    show(p.quality_dimensions(result))
    show(p.missingness(result))
    show(p.issue_matrix(result))


def with_target(result: AnalysisResult, target: str | None) -> AnalysisResult:
    if target is None or target not in result.ingestion.table.columns:
        return result
    readiness = assess_readiness(
        result.ingestion.table,
        result.semantic,
        result.profile,
        result.analytics,
        target_name=target,
    )
    return replace(result, readiness=readiness)


def readiness(result: AnalysisResult) -> None:
    page_header("AI Readiness", "Assess your dataset’s suitability for machine learning.")
    options = [None, *[c.column_name for c in result.profile.columns]]
    saved = st.session_state.get("visual_selected_target")
    target = st.selectbox(
        "Optional prediction target",
        options,
        index=options.index(saved) if saved in options else 0,
        format_func=lambda value: "No target selected" if value is None else value,
        key="readiness_target",
    )
    # Keep the selection after Streamlit cleans up widgets on other pages.
    st.session_state.visual_selected_target = target
    active = with_target(result, target)
    pair(p.readiness(active), p.readiness_dimensions(active))
    with st.expander("Readiness measurements"):
        st.dataframe(
            pd.DataFrame(
                [
                    {
                        "Dimension": d.name.replace("_", " ").title(),
                        "Score": d.score,
                        "Measurement": d.measurement,
                    }
                    for d in active.readiness.dimensions
                ]
            ),
            hide_index=True,
            use_container_width=True,
        )
    if active.readiness.blockers:
        st.warning("Preparation blockers: " + "; ".join(active.readiness.blockers))
    if active.readiness.warnings:
        with st.expander("Readiness observations"):
            for warning in active.readiness.warnings:
                st.write(warning)
    st.markdown("### Target analysis")
    analysis = active.readiness.target
    if analysis is None:
        st.info(
            "Select an optional prediction target to inspect its distribution and relationships."
        )
        return
    st.write(f"Selected target: {analysis.target_name} · {analysis.target_kind.replace('_', ' ')}")
    for observation in analysis.observations:
        st.info(observation)
    numeric = [name for name in p.numeric_names(active) if name != target]
    classification = analysis.target_kind == "classification_candidate"
    feature = st.selectbox(
        "Numeric predictor",
        [None, *numeric],
        index=1 if numeric else 0,
        format_func=lambda value: "No numeric predictor" if value is None else value,
        key="visual_readiness_feature",
    )
    distribution = (
        p.frequency(active, analysis.target_name, title="Target distribution · class frequencies")
        if classification
        else p.histogram(active, analysis.target_name, title="Target distribution")
    )
    target_box = (
        p.box(active, feature, target=analysis.target_name)
        if classification and feature
        else p.box(active, analysis.target_name)
        if not classification
        else p.Chart(
            "Feature by target class", "box", empty="Not applicable: no numeric predictor selected."
        )
    )
    pair(distribution, target_box)
    first, second = st.columns(2)
    with first:
        if feature and not classification:
            show(p.scatter(active, feature, analysis.target_name))
        elif feature and classification:
            others = [name for name in numeric if name != feature]
            if others:
                other = st.selectbox(
                    "Second numeric predictor", others, key="visual_readiness_other"
                )
                show(p.scatter(active, feature, other, target=analysis.target_name))
            else:
                show(
                    p.Chart(
                        "Feature vs target",
                        "scatter",
                        empty="Not applicable: class-aware scatter requires two numeric predictors.",
                    )
                )
        else:
            show(
                p.Chart(
                    "Feature vs target",
                    "scatter",
                    empty="Not applicable: no numeric predictor available.",
                )
            )
    with second:
        categories = [name for name in p.categorical_names(active) if name != target]
        if categories:
            category = st.selectbox(
                "Categorical predictor", categories, key="visual_readiness_category"
            )
            show(p.frequency(active, category, title="Predictor frequencies"))
        else:
            show(
                p.Chart(
                    "Predictor frequencies",
                    "bar",
                    empty="Not applicable: no categorical predictor available.",
                )
            )


def column(result: AnalysisResult, name: str | None = None) -> None:
    metadata, distribution_card, missing_card = st.columns([1, 1.4, 1.2])
    with metadata, st.container(border=True):
        names = [c.column_name for c in result.profile.columns]
        name = (
            name
            if name is not None
            else st.selectbox("Select a column", names, key="selected_column")
        )
        profile = next(c for c in result.profile.columns if c.column_name == name)
        st.write("**Type:** " + profile.semantic_type.value.replace("_", " "))
        st.write("**Data type:** " + profile.physical_dtype)
        st.write(f"Missing: {profile.null_count:,} ({profile.missing_percentage:.1f}%)")
        st.write(f"Unique values: {profile.unique_count:,}")
        if profile.statistics and profile.statistics.kind == "numeric":
            st.write(
                f"Mean: {profile.statistics.mean:,.3g}"
                if profile.statistics.mean is not None
                else "Mean: unavailable"
            )
            st.write(
                f"Median: {profile.statistics.median:,.3g}"
                if profile.statistics.median is not None
                else "Median: unavailable"
            )
    numeric = name in p.numeric_names(result)
    distribution = (
        p.histogram(result, name)
        if numeric
        else p.frequency(result, name)
        if name in p.categorical_names(result)
        else p.Chart(
            "Distribution",
            "bar",
            empty="Not applicable: this column has no numeric or categorical profile.",
        )
    )
    with distribution_card:
        show(distribution)
    with missing_card:
        missing = p.missing_present(result, name)
        show(
            replace(
                missing,
                kind="ring",
                marks=tuple(
                    replace(m, group="health" if m.label == "Present" else "critical")
                    for m in missing.marks
                ),
                x_label="values",
            )
        )
    pair(p.box(result, name), p.column_quality(result, name))


def recommendations(result: AnalysisResult) -> None:
    pair(p.recommendation_dimensions(result), p.affected_columns(result))
    matrix, priority = st.columns([1.6, 1])
    with matrix, st.container(border=True):
        st.markdown("### Issue → action matrix")
        rows, total = p.action_links(result)
        if rows:
            st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)
            st.caption(
                f"Showing {len(rows)} of {total} source-finding/action links. Affected percentages have finding-specific denominators and must not be summed."
            )
        else:
            st.info("No linked remediation actions are available.")
    with priority:
        show(p.remediation(result))
