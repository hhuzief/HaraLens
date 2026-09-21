"""Dependency-free, escaped SVG documents shared by Streamlit and exported reports."""

from __future__ import annotations

import math
from html import escape

from .prepare import Chart

COLORS = {
    "background": "#ffffff",
    "surface": "#edf2f7",
    "text": "#172033",
    "muted": "#4b586c",
    "border": "#8592a3",
    "health": "#08756a",
    "readiness": "#6842a6",
    "neutral": "#1456a0",
    "warning": "#a54313",
    "critical": "#be2638",
    "medium": "#957000",
    "secondary": "#397e90",
}
INK = {name: f"var(--chart-{name})" for name in COLORS}
CHART_CSS = (
    ".hl-chart {"
    + ";".join(f"--chart-{name}:{color}" for name, color in COLORS.items())
    + "}"
    + """
.hl-chart { color-scheme: only light; background: var(--chart-background); color: var(--chart-text);
  font: 14px/1.5 Arial,sans-serif; border: 1px solid var(--chart-border); border-radius: 12px;
  padding: 20px; margin: 0 0 16px; overflow-wrap: anywhere; break-inside: avoid; }
.hl-chart h3 { color: var(--chart-text); margin: 0 0 8px; font-size: 18px; }
.hl-chart p, .hl-chart figcaption { color: var(--chart-muted); margin: 8px 0 0; font-size: 13px; }
.hl-chart .hl-plot { overflow-x: auto; }
.hl-chart svg { display: block; width: 100%; min-width: 580px; height: auto; }
.hl-chart svg text { font: 14px Arial,sans-serif; fill: var(--chart-text); }
.hl-chart .hl-empty { padding: 36px 12px; background: var(--chart-surface); color: var(--chart-text); }
.hl-chart .hl-plot:focus-visible { outline: 2px solid var(--chart-neutral); }
@media print {
  .hl-chart { border-radius: 0; padding: 10px; }
  .hl-chart svg { min-width: 0; }
  .hl-chart .hl-plot { overflow: visible; }
}
"""
)


def _short(value: str, limit: int = 34) -> str:
    return value if len(value) <= limit else value[: limit - 1] + "…"


def _text(x: float, y: float, value: str, *, anchor: str = "start", size: int = 14) -> str:
    return (
        f'<text x="{x:.2f}" y="{y:.2f}" text-anchor="{anchor}" style="font-size:{size}px">'
        f"<title>{escape(value[:300])}</title>{escape(_short(value))}</text>"
    )


def _rect(x: float, y: float, width: float, height: float, color: str, detail: str = "") -> str:
    return (
        f'<rect x="{x:.2f}" y="{y:.2f}" width="{max(0, width):.2f}" height="{height:.2f}" '
        f'fill="{color}"><title>{escape(detail[:400])}</title></rect>'
    )


def _line(x1: float, y1: float, x2: float, y2: float, color: str = INK["border"]) -> str:
    return f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="{color}" stroke-width="2"/>'


def _number(value: float) -> str:
    return f"{value:,.3g}"


def _bars(chart: Chart) -> tuple[str, int]:
    height = max(180, 55 + len(chart.marks) * 44)
    maximum = chart.maximum or max((m.value or 0 for m in chart.marks), default=1) or 1
    parts = []
    for i, mark in enumerate(chart.marks):
        y = 20 + i * 44
        parts.append(_text(0, y + 15, mark.label))
        parts.append(_rect(280, y, 320, 18, INK["surface"]))
        if mark.value is not None:
            parts.append(
                _rect(
                    280,
                    y,
                    320 * mark.value / maximum,
                    18,
                    INK[mark.group]
                    if mark.group in {"critical", "warning", "medium", "health"}
                    else INK[chart.accent],
                    mark.detail,
                )
            )
        label = "Not evaluated" if mark.value is None else _number(mark.value)
        parts.append(_text(610, y + 15, label))
        if mark.detail:
            parts.append(_text(280, y + 36, mark.detail, size=12))
    parts.extend(
        (
            _text(280, height - 8, "0"),
            _text(600, height - 8, _number(maximum), anchor="end"),
            _text(440, height - 8, chart.x_label, anchor="middle", size=12),
        )
    )
    return "".join(parts), height


def _donut(chart: Chart) -> tuple[str, int]:
    mark = chart.marks[0]
    circumference = 2 * math.pi * 88
    parts = [
        f'<circle cx="210" cy="125" r="88" fill="none" stroke="{INK["surface"]}" stroke-width="20"/>'
    ]
    if mark.value is not None:
        parts.append(
            f'<circle cx="210" cy="125" r="88" fill="none" stroke="{INK[chart.accent]}" stroke-width="20" '
            f'stroke-dasharray="{circumference * mark.value / 100:.2f} {circumference:.2f}" transform="rotate(-90 210 125)"/>'
        )
    parts.append(
        _text(
            210,
            135,
            f"{mark.value:.1f}" if mark.value is not None else "N/E",
            anchor="middle",
            size=27,
        )
    )
    parts.append(_text(210, 160, "/ 100", anchor="middle", size=14))
    parts.append(_text(350, 125, mark.detail, size=22))
    return "".join(parts), 280


def _ring(chart: Chart) -> tuple[str, int]:
    total = sum(m.value or 0 for m in chart.marks)
    circumference = 2 * math.pi * 85
    parts = [
        f'<circle cx="165" cy="135" r="85" fill="none" stroke="{INK["surface"]}" stroke-width="26"/>'
    ]
    offset = 0.0
    palette = ("neutral", "health", "secondary", "readiness")
    for i, mark in enumerate(chart.marks):
        amount = circumference * (mark.value or 0) / total if total else 0
        color = INK[mark.group] if mark.group in INK else INK[palette[i % len(palette)]]
        parts.append(
            f'<circle cx="165" cy="135" r="85" fill="none" stroke="{color}" stroke-width="26" stroke-dasharray="{amount:.3f} {circumference:.3f}" stroke-dashoffset="{-offset:.3f}" transform="rotate(-90 165 135)"><title>{escape(mark.label)}: {mark.value}</title></circle>'
        )
        offset += amount
        y = 35 + i * 28
        parts.append(_rect(310, y - 10, 10, 10, color))
        parts.append(_text(330, y, f"{mark.label}: {_number(mark.value or 0)}", size=15))
    parts.append(_text(165, 135, _number(total), anchor="middle", size=30))
    parts.append(_text(165, 159, chart.x_label, anchor="middle"))
    return "".join(parts), max(270, 45 + len(chart.marks) * 28)


def _radar(chart: Chart) -> tuple[str, int]:
    parts: list[str] = []
    count = len(chart.marks)

    def point(index: int, radius: float) -> tuple[float, float]:
        angle = 2 * math.pi * index / count - math.pi / 2
        return 350 + radius * math.cos(angle), 175 + radius * math.sin(angle)

    for value in (25, 50, 75, 100):
        points = " ".join(
            f"{x:.2f},{y:.2f}" for x, y in (point(i, value * 1.15) for i in range(count))
        )
        parts.append(f'<polygon points="{points}" fill="none" stroke="{INK["border"]}"/>')
        parts.append(_text(355, 175 - value * 1.15, str(value), size=11))
    for i, mark in enumerate(chart.marks):
        x, y = point(i, 115)
        parts.append(_line(350, 175, x, y))
        lx, ly = point(i, 140)
        parts.append(_text(lx, ly, str(i + 1), anchor="middle", size=14))
        parts.append(
            _text(
                15 + (i % 2) * 350,
                355 + (i // 2) * 24,
                f"{i + 1}. {mark.label}: {mark.value:g}",
                size=13,
            )
        )
    points = " ".join(
        f"{x:.2f},{y:.2f}"
        for x, y in (point(i, (m.value or 0) * 1.15) for i, m in enumerate(chart.marks))
    )
    parts.append(
        f'<polygon points="{points}" fill="{INK[chart.accent]}" fill-opacity="0.15" stroke="{INK[chart.accent]}" stroke-width="3"/>'
    )
    return "".join(parts), 360 + math.ceil(count / 2) * 24


def _heatmap(chart: Chart) -> tuple[str, int]:
    columns = list(dict.fromkeys(m.label for m in chart.marks))
    rows = list(dict.fromkeys(m.group for m in chart.marks))
    missingness = chart.maximum == 1
    cell_width = 480 / max(1, len(columns))
    cell_height = 3 if missingness else 25
    top = 135
    parts = []
    for j, column in enumerate(columns):
        x = 190 + j * cell_width + cell_width / 2
        parts.append(
            f'<g transform="translate({x:.2f} 120) rotate(-50)">{_text(0, 0, _short(column, 22), size=12)}</g>'
        )
    lookup = {name: j for j, name in enumerate(columns)}
    row_lookup = {name: i for i, name in enumerate(rows)}
    for i, row in enumerate(rows):
        if not missingness or i % 5 == 0 or i == len(rows) - 1:
            parts.append(
                _text(180, top + i * cell_height + cell_height * 0.8, row, anchor="end", size=12)
            )
    for mark in chart.marks:
        x = 190 + lookup[mark.label] * cell_width
        y = top + row_lookup[mark.group] * cell_height
        value = int(mark.value or 0)
        color = (
            (INK["neutral"] if value else INK["surface"])
            if missingness
            else INK[("surface", "health", "medium", "warning", "critical")[value]]
        )
        symbol = ("M" if value else "·") if missingness else ("·", "L", "M", "H", "C")[value]
        parts.append(
            _rect(
                x,
                y,
                cell_width - 1,
                cell_height - 1,
                color,
                f"{mark.group} / {mark.label}: {mark.detail}",
            )
        )
        parts.append(
            f'<text x="{x + cell_width / 2:.2f}" y="{y + cell_height * 0.8:.2f}" text-anchor="middle" '
            f'style="font-size:{8 if missingness else 12}px;fill:{INK["background"] if value else INK["text"]}">{symbol}</text>'
        )
    return "".join(parts), top + len(rows) * cell_height + 20


def _histogram(chart: Chart) -> tuple[str, int]:
    maximum = max(m.value or 0 for m in chart.marks) or 1
    parts = [_line(65, 270, 675, 270), _line(65, 20, 65, 270)]
    width = 600 / len(chart.marks)
    for i, mark in enumerate(chart.marks):
        height = 240 * (mark.value or 0) / maximum
        low, high = mark.coordinates
        parts.append(
            _rect(
                70 + i * width,
                270 - height,
                width - 2,
                height,
                INK[chart.accent],
                f"{_number(low)} to {_number(high)}: {mark.value:g} observations",
            )
        )
    for fraction in (0, 0.5, 1):
        parts.append(
            _text(58, 270 - 240 * fraction, _number(maximum * fraction), anchor="end", size=12)
        )
    parts.extend(
        (
            _text(70, 295, _number(chart.marks[0].coordinates[0])),
            _text(675, 295, _number(chart.marks[-1].coordinates[1]), anchor="end"),
            _text(350, 325, chart.x_label, anchor="middle"),
            _text(10, 15, "Count"),
        )
    )
    return "".join(parts), 340


def _scale(values: list[float]) -> tuple[float, float, float]:
    # Return normalized bounds/scale; callers divide before subtracting.
    factor = max(max(abs(value) for value in values), 1)
    low, high = min(values) / factor, max(values) / factor
    return low, high if high != low else low + 1, factor


def _boxes(chart: Chart) -> tuple[str, int]:
    values = [v for mark in chart.marks for v in mark.coordinates]
    low, high, factor = _scale(values)

    def x(value: float) -> float:
        return 220 + 430 * (value / factor - low) / (high - low)

    parts: list[str] = []
    for i, mark in enumerate(chart.marks):
        y = 30 + i * 66
        lower, q1, median, q3, upper = mark.coordinates
        parts.extend(
            (
                _text(0, y + 4, mark.label),
                _line(x(lower), y, x(upper), y),
                _line(x(lower), y - 8, x(lower), y + 8),
                _line(x(upper), y - 8, x(upper), y + 8),
                _rect(
                    x(q1),
                    y - 12,
                    max(2, x(q3) - x(q1)),
                    24,
                    INK["neutral"],
                    f"Q1={q1:g}; median={median:g}; Q3={q3:g}; {mark.detail}",
                ),
                _line(x(median), y - 15, x(median), y + 15, INK["text"]),
                _text(220, y + 32, mark.detail, size=12),
            )
        )
    height = 50 + len(chart.marks) * 66
    parts.extend(
        (
            _text(220, height - 10, _number(min(values))),
            _text(650, height - 10, _number(max(values)), anchor="end"),
            _text(440, height - 10, chart.x_label, anchor="middle", size=12),
        )
    )
    return "".join(parts), height


def _scatter(chart: Chart) -> tuple[str, int]:
    xs = [m.value for m in chart.marks if m.value is not None]
    ys = [m.coordinates[0] for m in chart.marks]
    xlow, xhigh, xf = _scale(xs)
    ylow, yhigh, yf = _scale(ys)
    parts = [_line(70, 260, 670, 260), _line(70, 25, 70, 260)]
    for mark in chart.marks:
        x = 70 + 590 * ((mark.value or 0) / xf - xlow) / (xhigh - xlow)
        y = 260 - 220 * (mark.coordinates[0] / yf - ylow) / (yhigh - ylow)
        label = mark.group.replace("Class ", "")
        if label:
            parts.append(_text(x, y, label, anchor="middle", size=11))
        else:
            parts.append(
                f'<circle cx="{x:.2f}" cy="{y:.2f}" r="3" fill="{INK["neutral"]}" fill-opacity="0.6"/>'
            )
    parts.extend(
        (
            _text(70, 280, _number(min(xs))),
            _text(660, 280, _number(max(xs)), anchor="end"),
            _text(62, 260, _number(min(ys)), anchor="end", size=12),
            _text(62, 40, _number(max(ys)), anchor="end", size=12),
            _text(350, 315, chart.x_label, anchor="middle"),
            _text(75, 17, chart.y_label),
        )
    )
    return "".join(parts), 330


def render_chart(chart: Chart) -> str:
    """Render a bounded chart fragment without JavaScript or external resources."""
    renderers = {
        "bar": _bars,
        "ring": _ring,
        "donut": _donut,
        "radar": _radar,
        "heatmap": _heatmap,
        "histogram": _histogram,
        "box": _boxes,
        "scatter": _scatter,
    }
    if chart.marks:
        content, height = renderers[chart.kind](chart)
        body = (
            f'<div class="hl-plot" tabindex="0" role="region" aria-label="{escape(chart.title, quote=True)}">'
            f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 700 {height}" role="img" '
            f'aria-label="{escape(chart.title, quote=True)}"><title>{escape(chart.title)}</title>'
            f"<desc>{escape(chart.caption[:1200])}</desc>{content}</svg></div>"
        )
    else:
        body = f'<p class="hl-empty">{escape(chart.empty)}</p>'
    return (
        f'<figure class="hl-chart"><h3>{escape(chart.title)}</h3>{body}'
        f"<figcaption>{escape(chart.caption[:1200])}</figcaption></figure>"
    )


def chart_document(chart: Chart, *, dark: bool = False) -> str:
    if dark:
        from .theme import DARK, DASHBOARD_CSS

        tokens = ";".join(f"--chart-{name}:{color}" for name, color in DARK.items())
        fragment = render_chart(chart)
        if chart.kind == "heatmap":
            fragment = fragment.replace('class="hl-chart"', 'class="hl-chart matrix"', 1)
        if chart.kind in {"bar", "box"} and len(chart.marks) > 7:
            fragment = fragment.replace('class="hl-chart"', 'class="hl-chart dense"', 1)
        return (
            "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
            "<meta name='viewport' content='width=device-width, initial-scale=1'>"
            f"<style>{CHART_CSS}.hl-chart{{{tokens}}}{DASHBOARD_CSS}</style>"
            f"</head><body>{fragment}</body></html>"
        )

    return (
        "<!doctype html><html lang='en'><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width, initial-scale=1'>"
        "<meta name='color-scheme' content='only light'>"
        f"<style>html,body{{margin:0;background:{COLORS['background']};color:{COLORS['text']}}}{CHART_CSS}</style>"
        f"</head><body>{render_chart(chart)}</body></html>"
    )
