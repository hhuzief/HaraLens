"""Exercise the active page functions, selectors, exports, and reset lifecycle."""

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

APP = Path(__file__).resolve().parents[2] / "apps/streamlit/app.py"
CSV = (
    "x,y,class,region\n"
    + "\n".join(
        f"{i * 1.2},{i * 0.6 + i % 3},{'A' if i % 3 else 'B'},{'East' if i % 2 else 'West'}"
        for i in range(40)
    )
).encode()


def page_script(function: str, target: str | None = None) -> str:
    return f"""
import runpy
import streamlit as st
from haralens.application import analyze_uploaded_dataset
namespace = runpy.run_path({str(APP)!r})
result = analyze_uploaded_dataset({CSV!r}, 'test.csv')
st.session_state.analysis_result = result
st.session_state.readiness_target = {target!r}
namespace[{function!r}](result)
"""


@pytest.mark.parametrize(
    "function,minimum",
    [
        ("_render_overview", 6),
        ("_render_quality", 3),
        ("_render_columns", 4),
        ("_render_recommendations", 3),
        ("_render_readiness", 2),
    ],
)
def test_active_pages_render_charts(function: str, minimum: int) -> None:
    app = AppTest.from_string(page_script(function)).run(timeout=30)
    assert not app.exception
    assert len(app.get("iframe")) >= minimum
    if function == "_render_overview":
        documents = [item.proto.srcdoc for item in app.get("iframe")]
        assert sum("<h3>Semantic type distribution" in doc for doc in documents) == 1
        assert sum("<h3>Issues by severity" in doc for doc in documents) == 1
        assert sum("<h3>Top columns by missingness" in doc for doc in documents) == 1
    if function == "_render_readiness":
        assert any("Select an optional prediction target" in item.value for item in app.info)


@pytest.mark.parametrize("target", ["class", "y"])
def test_readiness_target_dashboard_and_export(target: str) -> None:
    app = AppTest.from_string(page_script("_render_readiness", target)).run(timeout=30)
    assert not app.exception
    documents = [element.proto.srcdoc for element in app.get("iframe")]
    assert len(documents) == 6
    assert sum("<h3>Target distribution" in document for document in documents) == 1
    assert any("<h3>Predictor frequencies" in document for document in documents)
    assert any("<h3>Feature" in document for document in documents)


def test_explore_existing_tabs_and_relationships_preserved() -> None:
    app = AppTest.from_string(page_script("_render_explore")).run(timeout=30)
    assert not app.exception
    assert [tab.label for tab in app.tabs] == ["Distributions", "Relationships", "Missingness"]
    assert len(app.get("vega_lite_chart")) == 2
    assert any("Pearson correlation" in item.value for item in app.caption)


def test_reset_clears_visual_and_target_state_only() -> None:
    script = (
        page_script("_render_overview")
        + """
st.session_state.visual_readiness_feature = 'x'
st.session_state.selected_column = 'y'
st.session_state.unrelated_preference = 'retain'
namespace['_reset']()
assert st.session_state.analysis_result is None
assert 'visual_readiness_feature' not in st.session_state
assert 'readiness_target' not in st.session_state
assert 'selected_column' not in st.session_state
assert st.session_state.unrelated_preference == 'retain'
"""
    )
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception


def test_target_name_matching_old_empty_state_is_selectable() -> None:
    script = page_script("_render_readiness", "class").replace("class", "No target selected")
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    assert any("<h3>Target distribution" in element.proto.srcdoc for element in app.get("iframe"))


def test_target_survives_page_widget_cleanup_and_report_reruns() -> None:
    script = f"""
import runpy
import streamlit as st
from haralens.application import analyze_uploaded_dataset
namespace = runpy.run_path({str(APP)!r})
if st.session_state.analysis_result is None:
    st.session_state.analysis_result = analyze_uploaded_dataset({CSV!r}, 'test.csv')
mode = st.radio('Test page', ['Readiness', 'Report'])
if mode == 'Readiness':
    namespace['_render_readiness'](st.session_state.analysis_result)
else:
    namespace['report_page']()
"""
    app = AppTest.from_string(script).run(timeout=30)
    app.selectbox(key="readiness_target").set_value("class").run()
    assert not app.exception
    assert app.session_state.visual_selected_target == "class"
    app.radio[0].set_value("Report").run()
    app.run()
    assert not app.exception
    assert any("<h3>Target distribution" in item.proto.srcdoc for item in app.get("iframe"))


@pytest.mark.parametrize(
    "content",
    [
        b"category\na\nb\na\n",
        b'empty\n""\n""\n',
        b"numeric\n1\n2\n3\n",
    ],
)
def test_readiness_and_columns_handle_unsuitable_data(content: bytes) -> None:
    script = f"""
import streamlit as st
from haralens.application import analyze_uploaded_dataset
from haralens.visualization import dashboard
result = analyze_uploaded_dataset({content!r}, 'adaptive.csv')
name = result.profile.columns[0].column_name
st.session_state.readiness_target = name
dashboard.readiness(result)
dashboard.column(result, name)
"""
    app = AppTest.from_string(script).run(timeout=30)
    assert not app.exception
    assert len(app.get("iframe")) >= 8
