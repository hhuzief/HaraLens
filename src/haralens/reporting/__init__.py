"""Safe reusable HTML report generation."""

import re
from html import escape
from pathlib import PurePath

from haralens.application import AnalysisResult


def safe_report_filename(source_name: str) -> str:
    """Return a deterministic download name without path separators or traversal."""

    stem = PurePath(source_name.replace("\\", "/")).stem
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-") or "dataset"
    return f"haralens_report_{safe}.html"


def build_html_report(result: AnalysisResult) -> str:
    """Build a raw-row-free report suitable for download or later PDF conversion."""

    summary = result.profile.summary
    rows = "".join(
        f"<tr><td>{escape(item.name)}</td><td>{item.score:.1f}</td><td>{escape(item.measurement)}</td></tr>"
        for item in result.readiness.dimensions
    )
    insights = (
        "".join(
            f"<li><strong>{escape(item.title)}</strong>: {escape(item.message)}</li>"
            for item in result.insights.insights[: result.insights.display_limit]
        )
        or "<li>No deterministic insights were generated.</li>"
    )
    return f"""<!doctype html><html><head><meta charset='utf-8'><title>HaraLens report</title>
<style>body{{font-family:Arial,sans-serif;max-width:960px;margin:40px auto;color:#172033}}table{{border-collapse:collapse;width:100%}}td,th{{border:1px solid #d8dee9;padding:8px;text-align:left}}.score{{font-size:2em;font-weight:700}}</style></head>
<body><h1>HaraLens v0.1 report</h1><p>Dataset: {escape(result.source_name)}</p>
<h2>Executive summary</h2><p>Rows: {summary.row_count:,} · Columns: {summary.column_count:,}</p>
<p class='score'>Data Health: {result.health.overall_score if result.health.overall_score is not None else "Not evaluated"}</p>
<p class='score'>AI Readiness: {result.readiness.overall_score:.1f} ({escape(result.readiness.band.value)})</p>
<h2>AI readiness dimensions</h2><table><tr><th>Dimension</th><th>Score</th><th>Measurement</th></tr>{rows}</table>
<h2>Top insights</h2><ul>{insights}</ul>
<h2>Methodology</h2><p>Scores and observations are deterministic and descriptive. Correlation does not imply causation; potential outliers are not automatically errors. HaraLens does not assess label validity, sampling bias, deployment representativeness, or causal validity.</p>
</body></html>"""


__all__ = ["build_html_report", "safe_report_filename"]
