"""Regression checks for a self-contained, readable report document."""

import re
from html.parser import HTMLParser

from haralens.application import analyze_uploaded_dataset
from haralens.reporting import build_html_report
from haralens.reporting.styles import REPORT_CSS


def _luminance(color: str) -> float:
    channels = [int(color[i : i + 2], 16) / 255 for i in (1, 3, 5)]
    linear = [c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return sum(c * weight for c, weight in zip(linear, (0.2126, 0.7152, 0.0722), strict=True))


def test_report_palette_contrast() -> None:
    tokens = dict(re.findall(r"--report-([\w-]+):\s*(#[0-9a-f]{6})", REPORT_CSS))
    for foreground in ("text", "muted", "heading", "accent"):
        for background in ("bg", "surface"):
            light = _luminance(tokens[background])
            dark = _luminance(tokens[foreground])
            assert (light + 0.05) / (dark + 0.05) >= 4.5, (foreground, background)
    assert tokens["bg"] == "#ffffff"


def test_report_core_surfaces_are_explicit_and_theme_independent() -> None:
    screen_css = REPORT_CSS.split("@media", 1)[0]
    rules = dict(re.findall(r"([^{}]+)\{([^{}]*)\}", screen_css))
    normalized = {key.strip(): value for key, value in rules.items()}
    for selector in ("html, body", "table", "td", "th", ".score"):
        assert "background: var(--report-" in normalized[selector]
        assert "color: var(--report-" in normalized[selector]
    assert "color: var(--report-heading)" in normalized["h1, h2, h3, h4, h5, h6"]
    references = set(re.findall(r"var\((--[\w-]+)\)", REPORT_CSS))
    definitions = set(re.findall(r"(--[\w-]+):", REPORT_CSS))
    assert references <= definitions
    assert all(name.startswith("--report-") for name in references)
    assert "color-scheme: only light" in REPORT_CSS
    assert "transparent" not in REPORT_CSS
    assert "@media print" in REPORT_CSS
    assert "thead { display: table-header-group; }" in REPORT_CSS
    assert "table-layout: fixed" in REPORT_CSS
    assert "overflow-x: auto" in REPORT_CSS


class _DocumentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.tags: list[str] = []
        self.table_regions = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        self.tags.append(tag)
        attributes = dict(attrs)
        if attributes.get("class") == "table-scroll":
            assert attributes.get("tabindex") == "0"
            assert attributes.get("role") == "region"
            self.table_regions += 1


def test_canonical_document_retains_content_and_escapes_user_values() -> None:
    result = analyze_uploaded_dataset(
        b'"<script>alert(1)</script>",value\na,1\nb,2\nc,\n',
        '<img src=x onerror="alert(1)">.csv',
    )
    report = build_html_report(result)
    assert REPORT_CSS in report
    assert "<html lang='en'>" in report
    assert "name='viewport'" in report
    assert "name='color-scheme' content='only light'" in report
    assert "&lt;script&gt;alert(1)&lt;/script&gt;" in report
    assert "&lt;img src=x onerror=&quot;alert(1)&quot;&gt;.csv" in report
    assert f"{result.health.overall_score:.1f} / 100" in report
    assert f"{result.readiness.overall_score:.1f} / 100" in report
    for heading in (
        "Dataset overview",
        "Data Health",
        "Data-quality findings",
        "AI/ML Readiness",
        "Missing data analysis",
        "Statistical analysis",
        "Relationships",
        "Column profiles",
        "Analytical insights",
        "Recommendations",
        "Methodology and limitations",
    ):
        assert f"<h2>{heading}</h2>" in report
    parser = _DocumentParser()
    parser.feed(report)
    assert "script" not in parser.tags
    assert "img" not in parser.tags
    assert parser.table_regions == parser.tags.count("table") == 9
    assert parser.tags.count("thead") == parser.tags.count("tbody") == 9
