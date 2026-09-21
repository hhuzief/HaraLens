from __future__ import annotations

import pandas as pd

from haralens.analytics import analyze_frame
from haralens.application import analyze_uploaded_dataset
from haralens.insights import canonicalize_identifier_component
from haralens.readiness import ReadinessBand, assess_readiness
from haralens.reporting import build_html_report, safe_report_filename


def test_advanced_pipeline_is_deterministic_and_bounded() -> None:
    result = analyze_uploaded_dataset(
        b"id,x,y,segment\na,1,2,A\nb,2,4,A\nc,3,6,B\nd,100,200,B\n",
        "sample.csv",
    )
    assert result.analytics.numeric[0].outlier_count == 1
    assert result.analytics.correlations[0].coefficient > 0.99
    assert 0 <= result.readiness.overall_score <= 100
    assert result.readiness.band in tuple(ReadinessBand)
    assert result.insights.insights


def test_target_analysis_is_optional_and_conservative() -> None:
    result = analyze_uploaded_dataset(b"target,x\na,1\na,2\nb,3\n", "target.csv")
    target = assess_readiness(
        result.ingestion.table,
        result.semantic,
        result.profile,
        result.analytics,
        target_name="target",
    ).target
    assert target is not None
    assert target.target_kind == "classification_candidate"
    assert target.minority_ratio == 1 / 3


def test_report_contains_no_raw_rows() -> None:
    result = analyze_uploaded_dataset(b"secret,value\nCUSTOMER-123,1\n", "unsafe<script>.csv")
    report = build_html_report(result)
    assert "CUSTOMER-123" not in report
    assert "unsafe&lt;script&gt;.csv" in report
    assert "HaraLens v0.1 report" in report
    assert "Data Health &amp; AI Readiness Report" in report
    assert f"{result.readiness.overall_score:.1f} / 100" in report
    assert "Data-quality findings" in report
    assert "Recommendations" in report
    assert (
        safe_report_filename("../../customers<script>.csv")
        == "haralens_report_customers_script.html"
    )


def test_frame_analytics_skips_constant_correlation_columns() -> None:
    frame = pd.DataFrame({"a": [1, 1, 1], "b": [1, 2, 3]})
    result = analyze_uploaded_dataset(b"a,b\n1,1\n1,2\n1,3\n", "constant.csv")
    analytics = analyze_frame(frame, result.profile, result.semantic)
    assert analytics.correlations == ()


def test_insight_ids_are_safe_for_hostile_column_names() -> None:
    names = [
        "Deaths / 100 Cases",
        "Revenue ($)",
        "Growth %",
        "customer-id",
        "Total.Cost",
        "Age (Years)",
        "Revenue/Month",
        "Sales & Marketing",
        "Profit/Loss",
        "Column#1",
        "Question?",
        "A/B",
        "A-B",
        "A B",
        "Département",
        "你好",
        "🔥",
        "___",
        "   ",
    ]
    values = [canonicalize_identifier_component(name) for name in names]
    assert all(
        value and value.replace("_", "").isalnum() and value == value.upper() for value in values
    )
    safe_names = [name for name in names if name.strip() and name != "___"]
    header = ",".join(safe_names)
    rows = ",".join("1" for _ in safe_names)
    result = analyze_uploaded_dataset(f"{header}\n{rows}\n{rows}\n".encode(), "hostile.csv")
    ids = [item.id for item in result.insights.insights]
    assert all(value.replace("_", "").isalnum() and value == value.upper() for value in ids)
    assert len(ids) == len(set(ids))


def test_original_deaths_column_completes_analysis() -> None:
    result = analyze_uploaded_dataset(b"Deaths / 100 Cases,Revenue\n1,10\n2,20\n", "original.csv")
    assert result.insights.insights
    assert all("/" not in insight.id for insight in result.insights.insights)
