"""Truthfulness, bounds, privacy, and adaptive rendering of visual summaries."""

from dataclasses import replace

import pandas as pd
import pytest
from defusedxml import ElementTree

from haralens.application import AnalysisResult, analyze_uploaded_dataset
from haralens.reporting import build_html_report
from haralens.visualization import prepare as p
from haralens.visualization.dashboard import with_target
from haralens.visualization.render import CHART_CSS, COLORS, chart_document, render_chart


@pytest.fixture(scope="module")
def result() -> AnalysisResult:
    frame = pd.DataFrame(
        {
            "measure <&>": [i * 1.25 if i % 8 else None for i in range(80)],
            "outcome": [i * 0.8 + i % 4 for i in range(80)],
            "class": ["A" if i % 3 else "B" for i in range(80)],
            "region": ["East", "West"] * 40,
            "empty": [None] * 80,
            "constant": [7] * 80,
        }
    )
    return analyze_uploaded_dataset(frame.to_csv(index=False).encode(), "visuals.csv")


def test_scores_and_dimensions_are_canonical(result: AnalysisResult) -> None:
    assert p.health(result).marks[0].value == result.health.overall_score
    assert p.readiness(result).marks[0].value == result.readiness.overall_score
    assert [m.value for m in p.quality_dimensions(result).marks] == [
        d.score for d in result.health.dimensions
    ]
    assert [m.value for m in p.readiness_dimensions(result).marks] == [
        d.score for d in result.readiness.dimensions
    ]
    unavailable = replace(
        result,
        health=result.health.model_copy(update={"overall_score": None, "interpretation": None}),
    )
    assert "Not evaluated" in render_chart(p.health(unavailable))
    dimension = result.health.dimensions[0].model_copy(update={"score": None})
    unavailable = replace(
        result, health=result.health.model_copy(update={"dimensions": (dimension,)})
    )
    assert p.quality_dimensions(unavailable).marks[0].value is None
    assert "Not evaluated" in render_chart(p.quality_dimensions(unavailable))
    few = replace(
        result,
        readiness=result.readiness.model_copy(
            update={"dimensions": result.readiness.dimensions[:2]}
        ),
    )
    assert p.readiness_dimensions(few).kind == "bar"


def test_sampling_missingness_and_no_cell_values(result: AnalysisResult) -> None:
    chart = p.missingness(result)
    assert chart == p.missingness(result)
    assert len(chart.marks) <= p.HEAT_ROWS * p.HEAT_COLUMNS
    assert p.positions(100_000, 60)[-1] == 99_999
    assert len(set(p.positions(100_000, 60))) == 60
    for mark in chart.marks:
        row = int(mark.group.split()[1]) - 1
        assert mark.value == float(pd.isna(result.ingestion.table.iloc[row][mark.label]))
        assert mark.detail in {"Missing", "Present"}
    assert "sample" not in chart_document(chart).lower() or "sampling" in chart.caption.lower()


def test_issue_matrix_and_column_quality_match_findings(result: AnalysisResult) -> None:
    chart = p.issue_matrix(result)
    assert len(set(m.group for m in chart.marks)) <= p.ISSUE_COLUMNS
    for mark in chart.marks:
        relevant = [
            f
            for f in p.findings(result)
            if mark.group in p.scopes(f)
            and f.dimension.value.replace("_", " ").title() == mark.label
        ]
        assert mark.value == max((p.SEVERITY[f.severity.value] for f in relevant), default=0)
    for mark in p.column_quality(result, "empty").marks:
        assert mark.value == sum(
            "empty" in p.scopes(f) and f.dimension.value.replace("_", " ").title() == mark.label
            for f in p.findings(result)
        )


def test_histogram_counts_missing_and_canonical_box(result: AnalysisResult) -> None:
    name = "measure <&>"
    chart = p.histogram(result, name)
    assert sum(m.value or 0 for m in chart.marks) == len(p.finite(result.ingestion.table[name]))
    assert len(chart.marks) <= p.HISTOGRAM_BINS
    assert "10 missing" in chart.caption
    box = p.box(result, name)
    stats = next(c.statistics for c in result.profile.columns if c.column_name == name)
    assert stats is not None and stats.kind == "numeric"
    assert box.marks[0].coordinates[1:4] == (
        stats.first_quartile,
        stats.median,
        stats.third_quartile,
    )
    assert box.marks[0].value == next(
        n.outlier_count for n in result.analytics.numeric if n.column_name == name
    )
    assert not p.box(result, "class").marks
    assert not p.histogram(result, "empty").marks
    constant = p.histogram(result, "constant")
    assert len(constant.marks) == 1 and constant.marks[0].value == 80
    assert render_chart(constant)


def test_classification_target_charts(result: AnalysisResult) -> None:
    active = with_target(result, "class")
    assert active.readiness.target is not None
    assert active.readiness.target.target_kind == "classification_candidate"
    frequency = p.frequency(active, "class")
    assert [m.value for m in frequency.marks] == [53, 27]
    assert "66.2%" in frequency.marks[0].detail
    box = p.box(active, "measure <&>", target="class")
    assert len(box.marks) == 2
    for mark in box.marks:
        values = p.finite(
            result.ingestion.table.loc[
                result.ingestion.table["class"].eq(mark.label), "measure <&>"
            ]
        )
        assert mark.coordinates[2] == values.median()
    scatter = p.scatter(active, "measure <&>", "outcome", target="class")
    assert {m.group for m in scatter.marks} == {"Class 1", "Class 2"}
    assert all(len(m.coordinates) == 1 for m in scatter.marks)


def test_regression_target_and_no_target(result: AnalysisResult) -> None:
    assert with_target(result, None) is result
    assert with_target(result, "missing column") is result
    active = with_target(result, "outcome")
    assert active.readiness.target is not None
    assert active.readiness.target.target_kind == "regression_candidate"
    assert p.histogram(active, "outcome").marks
    assert p.scatter(active, "measure <&>", "outcome").marks
    assert not p.scatter(active, "outcome", "outcome").marks
    assert result.readiness.target is None  # original session result is untouched
    assert "Target distribution" in build_html_report(active)
    exported = build_html_report(with_target(result, "class"))
    assert "Category labels anonymized" in exported


def test_high_cardinality_and_scatter_bounds() -> None:
    frame = pd.DataFrame(
        {
            "category": [f"secret-{i}" for i in range(650)],
            "x": [i * 1.1 for i in range(650)],
            "y": [i * 0.7 for i in range(650)],
        }
    )
    result = analyze_uploaded_dataset(frame.to_csv(index=False).encode(), "wide.csv")
    frequency = p.frequency(result, "category")
    assert len(frequency.marks) == p.CATEGORIES + 1
    assert frequency.marks[-1].value == 640
    assert sum(m.value or 0 for m in frequency.marks) == 650
    assert "secret-" not in render_chart(p.frequency(result, "category", anonymize=True))
    scatter = p.scatter(result, "x", "y")
    assert len(scatter.marks) == p.SCATTER_POINTS
    assert scatter == p.scatter(result, "x", "y")
    assert len(p.box(result, "x", target="category").marks) == p.CATEGORIES
    assert len(p.scatter(result, "x", "y", target="category").marks) == p.CATEGORIES


def test_wide_dataset_bounds() -> None:
    frame = pd.DataFrame({f"column_{i}": [None, i, i, i] for i in range(30)})
    result = analyze_uploaded_dataset(frame.to_csv(index=False).encode(), "wide.csv")
    assert len(p.missingness(result).marks) == 4 * p.HEAT_COLUMNS
    assert len(p.issue_matrix(result).marks) <= p.ISSUE_COLUMNS * 6
    assert len(p.affected_columns(result).marks) <= p.ISSUE_COLUMNS
    assert len(p.remediation(result).marks) <= p.ISSUE_COLUMNS
    rows, total = p.action_links(result)
    assert len(rows) == min(total, p.ACTION_LINKS)


def test_recommendation_provenance_and_impact(result: AnalysisResult) -> None:
    recommendations = result.recommendations.recommendations
    assert sum(m.value or 0 for m in p.recommendation_dimensions(result).marks) == len(
        recommendations
    )
    rows, total = p.action_links(result)
    assert total == sum(len(r.source_finding_ids) for r in recommendations)
    by_id = {r.recommendation_id: r for r in recommendations}
    finding_by_id = {f.finding_id: f for f in p.findings(result)}
    for row in rows:
        assert isinstance(row["Recommendation ID"], str)
        assert isinstance(row["Finding ID"], str)
        rec = by_id[row["Recommendation ID"]]
        assert row["Finding ID"] in rec.source_finding_ids
        assert row["Issue"] == finding_by_id[row["Finding ID"]].message
        assert row["Action"] == rec.message
    ordered = sorted(
        recommendations, key=lambda r: (p.PRIORITY[r.priority.value], r.recommendation_id)
    )
    assert [m.value for m in p.remediation(result).marks] == [
        len(set(r.source_finding_ids)) for r in ordered[: p.ISSUE_COLUMNS]
    ]
    assert "not predicted score improvement" in p.remediation(result).caption
    ranked = p.ranked_columns(result)
    assert ranked == p.ranked_columns(result)


def test_all_charts_safe_svg_and_bounded(result: AnalysisResult) -> None:
    charts = (
        *p.report_charts(result),
        p.box(result, "measure <&>"),
        p.scatter(result, "measure <&>", "outcome"),
        p.missing_present(result, "empty"),
        p.column_quality(result, "class"),
        p.affected_columns(result),
        p.frequency(result, "class"),
    )
    for chart in charts:
        fragment = render_chart(chart)
        ElementTree.fromstring(fragment)  # generated markup remains well formed
        assert len(fragment.encode()) < 1_000_000
        assert "<script" not in fragment
        assert "javascript:" not in fragment
    assert "&lt;&amp;&gt;" in render_chart(p.histogram(result, "measure <&>"))
    assert "background:#ffffff;color:#172033" in chart_document(p.health(result))
    assert "color-scheme: only light" in CHART_CSS
    assert "@media print" in CHART_CSS
    assert COLORS["background"] == "#ffffff"


@pytest.mark.parametrize("content", [b"text\na\nb\na\n", b'empty\n""\n""\n', b"constant\n7\n7\n"])
def test_unsuitable_and_constant_datasets(content: bytes) -> None:
    result = analyze_uploaded_dataset(content, "adaptive.csv")
    for chart in p.report_charts(result):
        assert render_chart(chart)
    name = result.profile.columns[0].column_name
    assert p.missing_present(result, name).marks
    assert not p.scatter(result, name, name).marks


def test_chart_escaping_covers_attributes_and_text() -> None:
    attack = '<script>alert("x")</script>'
    chart = p.Chart(attack, "bar", (p.Mark(attack, 1, attack),), caption=attack)
    fragment = render_chart(chart)
    assert "<script>" not in fragment
    assert "&lt;script&gt;" in fragment
    ElementTree.fromstring(fragment)


def test_numeric_extremes_do_not_produce_invalid_coordinates(result: AnalysisResult) -> None:
    frame = result.ingestion.table.copy()
    frame["measure <&>"] = [-1e308, 1e308] * 40
    active = replace(result, ingestion=replace(result.ingestion, table=frame))
    for chart in (p.histogram(active, "measure <&>"), p.scatter(active, "measure <&>", "outcome")):
        rendered = render_chart(chart)
        assert '="nan' not in rendered and '="inf' not in rendered
        assert sum(m.value or 0 for m in chart.marks) == 80 if chart.kind == "histogram" else True


def test_theme_palette_text_contrast() -> None:
    def luminance(color: str) -> float:
        channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
        linear = [v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return sum(v * w for v, w in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))

    for background in ("background", "surface"):
        for foreground in ("text", "muted", "health", "readiness", "neutral", "warning"):
            assert (luminance(COLORS[background]) + 0.05) / (
                luminance(COLORS[foreground]) + 0.05
            ) >= 4.5


def test_preparation_does_not_mutate_analysis(result: AnalysisResult) -> None:
    before = result.ingestion.table.copy(deep=True)
    p.report_charts(result)
    p.box(result, "measure <&>", target="class")
    p.scatter(result, "measure <&>", "outcome", target="class")
    pd.testing.assert_frame_equal(result.ingestion.table, before)
    assert result.readiness.target is None


def test_sampling_limit_contract() -> None:
    assert p.positions(10, 1) == (0,)
    assert p.positions(0, 1) == ()
    with pytest.raises(ValueError, match="positive"):
        p.positions(10, 0)
