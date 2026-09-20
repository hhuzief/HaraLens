from pathlib import Path

from streamlit.testing.v1 import AppTest


def test_home_renders_and_reruns() -> None:
    path = Path(__file__).resolve().parents[2] / "apps/streamlit/app.py"
    app = AppTest.from_file(str(path)).run(timeout=30)
    assert not app.exception
    assert app.title[0].value == "HaraLens"
    assert "Phase 0" in app.info[0].value
    app.run()
    assert not app.exception
    assert len(app.title) == 1
    assert [page["page_name"] for page in app._registered_pages.values()] == [
        "Home",
        "Analyze",
        "Methodology / About",
    ]
