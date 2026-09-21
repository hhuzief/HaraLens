# Visual analytics

## Inventory before this expansion

| Active page | Existing visual/content | Source | Rendering function | Treatment |
| --- | --- | --- | --- | --- |
| Overview | Health metric/status; row/column/missing/duplicate metrics | Health score and profile summary | `_render_overview` | Preserved; added health donut |
| Overview | Dimension table, semantic-type bars, missingness table | Health dimensions, semantic counts, column profiles | `_render_overview` | Preserved |
| Data Quality | Severity metrics, filtered findings table, score-contribution explanation | Quality executions, health penalties | `_render_quality` | Preserved; added dimension bars, missingness heatmap, issue matrix |
| AI Readiness | Score/status, dimension table, blockers, optional target observations | Readiness result; `assess_readiness` | `_render_readiness` | Preserved in shared dashboard composition; added charts |
| Explore | Numeric value bars and statistics; selected-pair scatter and Pearson caption; missingness table | Ingested numeric columns, profiles, canonical correlation pairs | `_render_explore` | Unchanged |
| Columns | Selected column metadata table and statistics JSON | Column profile | `_render_columns` | Preserved; added applicable charts |
| Recommendations | Priority-grouped action list | Recommendation result | `_render_recommendations` | Preserved; added provenance-based summaries |
| Report | Light HTML document, scores, tables, findings, recommendations, limitations | `build_html_report` | `report_page` | Preserved; appended bounded visual summary |

No equivalent requested chart already existed on its destination page. The potential
duplicate is classification target distribution versus target-frequency bars: one
target-frequency chart serves both purposes. The extra frequency view describes a
different categorical predictor, when available. Explore had no categorical chart
or correlation heatmap to preserve; its actual existing capabilities remain intact.

## Architecture and design

`visualization.prepare` converts the canonical `AnalysisResult` into immutable
`Chart`/`Mark` descriptions. It does not calculate health or readiness scores.
Distribution counts, deterministic histogram bins, grouped descriptive quartiles,
and finite observation selection are visualization aggregation, not official scores.

`visualization.render` produces escaped, offline SVG/HTML. `visualization.dashboard`
composes native Streamlit selectors, two-column chart rows, details, and empty states.
The report consumes the same preparation and SVG renderer, with no Streamlit imports
needed for chart preparation or report generation. There are no additional packages,
JavaScript libraries, network assets, caches, or persistent dataset stores.

Charts deliberately use opaque white document cards in both app themes. Text,
backgrounds, grid lines, outlines, and health/readiness accents are explicit. Scores,
severity letters, class numbers, and counts communicate meaning without color alone.
SVG titles provide hover details; descriptions/captions explain bounds and unavailable
states. Wide charts scroll within their cards. Native selectors and existing charts
continue using Streamlit's theme. Print CSS removes minimum SVG widths and clipping.

## Data rules and bounds

| Visualization | Rule |
| --- | --- |
| Scores | Canonical score/status only; unavailable health remains “Not evaluated” |
| Quality dimensions | Methodology order, 0–100 common scale; null values have no bar |
| Radar | Actual readiness dimensions; fewer than three uses bars |
| Missingness | At most 60 evenly spaced original row positions × 20 columns with highest missingness; column-position tie break; booleans only |
| Issue matrix | Top 20 affected columns by maximum finding severity, finding count, name; multi-column findings affect each named column; dataset findings disclosed separately |
| Histogram | All finite values, at most 24 equal-width bins; `ceil(sqrt(n))` capped at 24, one bin for constants; missing/non-finite exclusions disclosed |
| Frequencies | Exact non-missing counts; top 10 plus Other; count descending with type/name tie breaks |
| Column box | Canonical Q1/median/Q3 and canonical IQR fences; observed in-fence whiskers; canonical outlier count, without raw outlier records |
| Grouped box | Top 10 target classes; finite feature observations; configured quantile interpolation, 1.5-IQR whiskers; descriptive group diagnostics only |
| Scatter | Up to 400 evenly spaced eligible finite pairs; classification limited to top 10 target classes, numbered in target-frequency order; no raw row IDs |
| Correlations | Existing engine pairs only; report selects up to 10 by absolute coefficient and preserves signed values |
| Recommendations | Top 20 affected columns/actions; issue/action table capped at 100 links, total disclosed |
| SVG payload | Bounded mark counts; hover text capped at 400 characters and captions at 1,200; labels shortened with hover detail |

Categorical values appear only where needed to interpret interactive frequency/group
charts. Exported target frequencies use category ranks instead of raw category names.
The report exports aggregate visualizations, never scatter records or raw outliers.
Empty, unsupported, non-finite-only, constant, and insufficient-variable cases have
explicit unavailable states. No target means no target-specific chart.

## Remediation methodology

No new impact score or predicted health improvement is calculated. Action bars show
the count of distinct `source_finding_ids` per recommendation, ordered by the engine's
priority (urgent, high, medium, low), then stable recommendation ID. Overlap between
actions is disclosed. Column ranking uses linked findings, maximum severity, finding
count, then name. This is an investigation order, not a universal column-quality score.

The issue/action table preserves both source finding and recommendation IDs, actual
messages, priority, affected scope, and available affected percentage. Percentages can
have different denominators and must not be summed. No actions are invented.

## Report selection

The report includes health, quality dimensions, bounded missingness, issue matrix,
readiness, readiness dimensions, the first applicable numeric profile's histogram,
up to 10 canonical correlation pairs, selected target distribution if present,
recommendations by dimension, and remediation evidence coverage. Selection is
deterministic and bounded to at most 11 charts. Existing text/tables remain intact.
Preview and download receive the same complete HTML string. The selected target is
session-scoped; reset clears target and visualization controls.

## Manual acceptance

Run `uv run --locked streamlit run apps/streamlit/app.py` and use the printed local URL.
Use the configured **HaraLens dark theme**, at desktop width and a narrower window.
If a personal Streamlit theme override is active, select the custom theme in Settings. Browser-based visual acceptance has not been performed by
the automated tests.

1. Upload a dataset with two numeric predictors, a categorical predictor, and a
   classification target. Include missing values and a long/special-character name.
2. **Overview:** compare both score donuts against the canonical result/report. Inspect
   the quality radar (bars when dimensions are unavailable), severity bars, semantic
   donut, and top missingness bars. Expand Profile details for the original tables.
3. **Data Quality:** inspect dimension bars, “Not evaluated” labels where applicable,
   missingness heatmap, and issue matrix. Hover cells and check sampling captions.
   Confirm severity filters, findings, and score-contribution explanations still work.
4. **AI Readiness:** initially confirm the no-target message. Select the classification
   target; inspect donut, radar, class frequencies, grouped box, predictor-pair scatter,
   and a different categorical predictor's frequency chart. Change numeric predictors.
   Confirm class numbers follow frequency order. Select a suitable regression target
   with more than 10 distinct numeric values; inspect its histogram, box, and feature
   versus target scatter. Scores must match the engine-produced metrics.
5. **Explore:** change distribution and X/Y selections; confirm numeric value bars,
   statistics, scatter/Pearson caption, and missingness table all remain functional.
   Inspect the histogram, categorical selector, all-computed-correlations table, and heatmap.
6. **Columns:** choose numeric, categorical, empty, and constant columns. Inspect
   histogram/frequency, missing/present counts and percentages, box/outlier count,
   quality-finding profile, original metadata, and statistics JSON.
7. **Recommendations:** compare dimension counts and affected-column ranking to the
   existing action list; inspect source IDs in issue/action links. Confirm remediation
   bars show linked findings rather than promised score gains.
8. **Report:** inspect the visual summary and original sections; download the HTML,
   open it offline, and compare it with preview. Check long labels and table scrolling.
   Print/Save as PDF and inspect charts, labels, and page breaks.
9. **Analyze another dataset:** confirm target/predictor/column selections reset.
   Repeat with no selected target, missing values, a dataset without numeric columns,
   one numeric column, no categorical predictors, high-cardinality categories, and a
   wide dataset. Verify empty states and truncation captions, with no exceptions.


## Approved-reference dashboard redesign

The application uses supported Streamlit theme configuration in `.streamlit/config.toml`,
including navy backgrounds, white text, blue active/analytical accents, cool borders,
compact headings, and a layered sidebar. `st.logo` puts the HaraLens/version lockup above
supported icon navigation; Methodology / About remains the final navigation item.
No application DOM selectors or custom navigation JavaScript are injected.

`visualization/theme.py` owns dashboard tokens and scoped card CSS. `render.py` uses
CSS-variable SVG colors so dashboard documents can select the dark palette while
report fragments retain the independent light palette. Bars, rings, radars, histograms,
boxes, scatterplots, and matrices share typography and colors. Critical/high/medium/low
use red/orange/amber/green and retain textual severity indicators. Large matrices and
dense rankings scroll within their chart area; captions disclose bounded selections.
The report HTML stays self-contained and printable, with its contrast protection intact.

Page composition:

- Overview: two score cards, quality dimensions/severity, semantic types/missingness;
  exact dataset counts, profile tables, insights, and risks remain available below.
- Data Quality: wide dimension scores, heatmap, issue matrix, then full finding filters
  and score explanations.
- AI Readiness: score/radar, target distribution/box, scatter/categorical frequency;
  optional target and predictor selectors retain session behavior. Canonical dimension
  measurements are in an expander; blockers and observations remain available.
- Explore: existing tabs, numeric sequence, statistics, scatter and correlation caption
  retained in bordered areas, with histogram, categorical frequency, all computed
  correlations, and missingness heatmap available through the same controls.
- Columns: selector/metadata, distribution, missing/present count ring; then outliers
  and canonical quality-finding counts. Full profile JSON remains in an expander.
- Recommendations: dimension/ranking pair, action matrix/priority pair, full action list.
- Report: consistent page heading followed by Preview and Download HaraLens Report.

Consolidations (no analytical information removed):

1. Overview standalone health metric/status consolidated into the canonical score donut.
2. Overview semantic bars replaced by one exact-count semantic donut.
3. Readiness standalone score/status consolidated into its canonical score donut.
4. Columns missing/present bars replaced by one exact-count donut; original percentages
   remain in metadata and ring tooltips. Complete metadata/statistics moved to the profile expander.
5. Overview dimension/missingness tables retained as expandable detail instead of
   competing with summary charts. Readiness measurements likewise remain expandable.

Automated acceptance covers canonical score/count sources, not-evaluated fallback,
dark/light renderer isolation, all page sections, target persistence, reset, report
availability, column changes, and numeric/categorical/missing/pristine/wide/high-cardinality/
classification/regression/special-character datasets. The deterministic engine, ingestion,
semantic inference, scoring, recommendation mathematics, resource limits and session
isolation were not changed by this redesign.

Validation on 2026-09-21: full pytest passed (510 tests), coverage 97.71% (85% required).
Strict mypy passed for 73 source files. Deployment/cloud import tests are included in
full pytest. Streamlit started successfully on http://localhost:8501 using the requested
`uv run --locked streamlit run apps/streamlit/app.py` command. The final Ruff, format,
pre-commit, and diff checks are recorded in the implementation handoff.

Limitations: this is a responsive Streamlit/SVG interpretation, not a pixel-perfect clone.
SVG plots provide native hover descriptions rather than Plotly-style zooming. Existing
bounded sampling, category grouping, and top-column/action limits remain disclosed.
The connected browser tool reported no available browser, so browser screenshot
comparison and desktop/narrow-window visual acceptance remain for the user. Existing
Streamlit component/width API and third-party test-client deprecation warnings remain;
they did not fail the suite. No commit or push was performed.
