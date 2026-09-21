"""Dashboard composition and adaptation, without pixel-coupled assertions."""

import tomllib
from dataclasses import replace
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

from haralens.application import analyze_uploaded_dataset
from haralens.visualization import prepare as p
from haralens.visualization.render import chart_document
from haralens.visualization.theme import DARK

ROOT = Path(__file__).resolve().parents[2]


def test_supported_dark_configuration_and_report_isolation() -> None:
    config = tomllib.loads((ROOT / ".streamlit/config.toml").read_text())
    assert config["theme"]["base"] == "dark"
    assert config["theme"]["primaryColor"] == DARK["neutral"]
    chart = p.Chart("Score", "donut", (p.Mark("Score", 43.2, "Needs attention"),))
    dark = chart_document(chart, dark=True)
    light = chart_document(chart)
    assert "43.2" in dark and "/ 100" in dark
    assert "--chart-background:" + DARK["background"] in dark
    assert "--chart-background:" + DARK["background"] not in light
    assert "color-scheme: only light" in light
    assert "color-scheme: dark" in dark


def test_overview_summaries_preserve_canonical_counts_and_unavailable_scores() -> None:
    result = analyze_uploaded_dataset(b"a,b\n1,x\n2,x\n,y\n", "counts.csv")
    dimensions, severity, semantics, missing = p.overview_summaries(result)
    assert [m.value for m in dimensions.marks] == [d.score for d in result.health.dimensions]
    assert sum(m.value or 0 for m in semantics.marks) == result.profile.summary.column_count
    assert sum(m.value or 0 for m in severity.marks) == len(p.findings(result))
    assert missing.marks[0].value == result.profile.columns[0].missing_percentage
    absent = result.health.dimensions[0].model_copy(update={"score": None})
    unavailable = replace(result, health=result.health.model_copy(update={"dimensions": (absent,)}))
    chart = p.overview_summaries(unavailable)[0]
    assert chart.kind == "bar"
    assert "Not evaluated" in chart_document(chart, dark=True)


def adaptive_frame(case: str) -> pd.DataFrame:
    base = pd.DataFrame(
        {"amount <&>": [i * 1.3 for i in range(40)], "value": range(40), "class": ["a", "b"] * 20}
    )
    if case == "categorical":
        return base[["class"]]
    if case == "missing":
        base.loc[::3, "amount <&>"] = None
    if case == "one_numeric":
        return base[["amount <&>"]]
    if case == "wide":
        return pd.DataFrame({f"column {i}": range(40) for i in range(45)})
    if case == "high_cardinality":
        return pd.DataFrame({"labels": [f"item <{i}>" for i in range(120)]})
    if case == "numeric":
        return base[["amount <&>", "value"]]
    return base


@pytest.mark.parametrize(
    "case",
    [
        "pristine",
        "numeric",
        "categorical",
        "missing",
        "one_numeric",
        "wide",
        "high_cardinality",
        "classification",
        "regression",
    ],
)
def test_all_dashboard_pages_adapt(case: str) -> None:
    content = adaptive_frame(case).to_csv(index=False).encode()
    target = "class" if case == "classification" else "amount <&>" if case == "regression" else None
    script = f"""
import runpy
import streamlit as st
from haralens.application import analyze_uploaded_dataset
namespace = runpy.run_path({str(ROOT / "apps/streamlit/app.py")!r})
result = analyze_uploaded_dataset({content!r}, "adaptive.csv")
st.session_state.analysis_result = result
st.session_state.readiness_target = {target!r}
for name in (
    "_render_overview", "_render_quality", "_render_readiness",
    "_render_explore", "_render_columns", "_render_recommendations"
):
    namespace[name](result)
"""
    app = AppTest.from_string(script).run(timeout=60)
    assert not app.exception
    documents = [item.proto.srcdoc for item in app.get("iframe")]
    assert len(documents) >= 18
    assert all("color-scheme: dark" in doc for doc in documents)
    assert any("<h3>Missing vs present" in doc for doc in documents)
    assert any("<h3>Column quality findings" in doc for doc in documents)


def test_column_selector_updates_profile_and_charts() -> None:
    script = f"""
import runpy
import streamlit as st
from haralens.application import analyze_uploaded_dataset
namespace = runpy.run_path({str(ROOT / "apps/streamlit/app.py")!r})
result = analyze_uploaded_dataset(b"value,category\\n1,a\\n2,b\\n3,a\\n", "columns.csv")
namespace["_render_columns"](result)
"""
    app = AppTest.from_string(script).run(timeout=30)
    app.selectbox(key="selected_column").set_value("category").run()
    assert not app.exception
    documents = [item.proto.srcdoc for item in app.get("iframe")]
    assert any("Not applicable: select a numeric column" in doc for doc in documents)
    assert any("category" in doc for doc in documents)
