"""Canonical light document theme, shared by iframe preview and HTML export."""

REPORT_CSS = """
:root {
  color-scheme: only light;
  --report-bg: #ffffff;
  --report-surface: #f2f5f9;
  --report-text: #172033;
  --report-muted: #4b586c;
  --report-border: #8592a3;
  --report-heading: #172033;
  --report-accent: #1456a0;
}
* { box-sizing: border-box; }
html, body { background: var(--report-bg); color: var(--report-text); }
body {
  font-family: Arial, sans-serif;
  max-width: 1100px;
  margin: 0 auto;
  padding: 32px 24px;
  line-height: 1.5;
  overflow-wrap: anywhere;
}
h1, h2, h3, h4, h5, h6 { color: var(--report-heading); line-height: 1.25; }
p, ul, ol, li, strong { color: var(--report-text); }
section { margin-top: 28px; }
a { color: var(--report-accent); text-decoration: underline; }
a:focus-visible, .table-scroll:focus-visible {
  outline: 2px solid var(--report-accent); outline-offset: 2px;
}
.table-scroll { max-width: 100%; overflow-x: auto; margin: 12px 0 28px; }
table { border-collapse: collapse; width: 100%; color: var(--report-text); background: var(--report-bg); }
td, th { border: 1px solid var(--report-border); padding: 8px; text-align: left; vertical-align: top; min-width: 7rem; }
th { color: var(--report-heading); background: var(--report-surface); }
td { color: var(--report-text); background: var(--report-bg); }
tbody tr:nth-child(even) td { background: var(--report-surface); }
.score { color: var(--report-heading); background: var(--report-surface); padding: 12px 16px; font-size: 1.6em; font-weight: 700; }
.note, caption, figcaption { color: var(--report-muted); font-size: .9em; }
@media (max-width: 600px) {
  body { padding: 20px 12px; }
  h1 { font-size: 1.7rem; }
  h2 { font-size: 1.3rem; }
}
@media print {
  @page { margin: 15mm; }
  html, body { background: var(--report-bg); color: var(--report-text); }
  body { max-width: none; margin: 0; padding: 0; font-size: 10pt; }
  .table-scroll { overflow: visible; }
  table { table-layout: fixed; }
  td, th { min-width: 0; overflow-wrap: anywhere; }
  thead { display: table-header-group; }
  tr, .score { break-inside: avoid; }
  h1, h2, h3 { break-after: avoid; }
  .score { background: var(--report-bg); padding: 0; }
}
"""
