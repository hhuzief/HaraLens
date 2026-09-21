from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace
from typing import Any

from haralens.application import analyze_uploaded_dataset


def _load_streamlit_app() -> Any:
    path = Path(__file__).resolve().parents[2] / "apps/streamlit/app.py"
    spec = importlib.util.spec_from_file_location("haralens_streamlit_app_under_test", path)
    if spec is None or spec.loader is None:
        raise AssertionError("could not load Streamlit app")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_overview_has_no_report_download_and_report_page_does() -> None:
    module = _load_streamlit_app()
    calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    fake_streamlit = SimpleNamespace(
        session_state={"analysis_result": None},
        title=lambda *args, **kwargs: None,
        markdown=lambda *args, **kwargs: None,
        write=lambda *args, **kwargs: None,
        info=lambda *args, **kwargs: None,
        download_button=lambda *args, **kwargs: calls.append((args, kwargs)),
    )
    module.st = fake_streamlit
    module.overview_page()
    assert calls == []

    result = analyze_uploaded_dataset(b"id,value\na,1\nb,2\n", "current.csv")
    fake_streamlit.session_state["analysis_result"] = result
    module._render_overview = lambda _result: None
    module.overview_page()
    assert calls == []

    events: list[str] = []
    fake_streamlit.title = lambda *args, **kwargs: events.append("title")
    fake_streamlit.write = lambda *args, **kwargs: events.append("write")
    fake_streamlit.caption = lambda *args, **kwargs: events.append("caption")
    fake_streamlit.markdown = lambda *args, **kwargs: events.append(str(args[0]))
    previews: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def capture_preview(*args: Any, **kwargs: Any) -> None:
        previews.append((args, kwargs))
        events.append("preview")

    module.components = SimpleNamespace(html=capture_preview)
    module.report_page()

    assert len(calls) == 1
    args, kwargs = calls[0]
    assert args == ("Download HaraLens Report",)
    assert kwargs["data"] == module.build_html_report(result)
    assert kwargs["file_name"] == "haralens_report_current.html"
    assert kwargs["mime"] == "text/html"
    assert previews == [((kwargs["data"],), {"height": 1100, "scrolling": True})]
    assert events.index("preview") < events.index("### Export Report")


def test_report_is_last_result_page_after_recommendations() -> None:
    module = _load_streamlit_app()
    module.st = SimpleNamespace(
        Page=lambda _page, *, title, default=False, icon=None: SimpleNamespace(
            title=title, default=default, icon=icon
        )
    )
    titles = [page.title for page in module._build_pages(object())]
    assert titles[-2:] == ["Report", "Methodology / About"]
    assert titles.index("Report") == titles.index("Recommendations") + 1
