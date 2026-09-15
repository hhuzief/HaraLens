# HARALENS — MASTER END-TO-END ENGINEERING PROMPT

You are acting as a principal software architect, senior backend engineer, senior frontend engineer, data scientist, machine-learning engineer, MLOps engineer, data-quality engineer, security engineer, DevOps engineer, UX engineer, QA engineer, database architect, statistical analyst, and technical product lead.

Your assignment is to design and build **HaraLens**, a professional, production-oriented, AI-assisted Data Health, Advanced Analytics, Data Quality, Machine Learning and Governance SaaS platform.

This is NOT a tutorial project.

This is NOT a single Streamlit script.

This is NOT a university dashboard.

This is NOT an excuse to produce excessive features with poor engineering.

The objective is to create a serious modular software product whose architecture, analytics methodology, code quality, security, testing, documentation and UX would withstand technical review by experienced software engineers, data scientists and analytics professionals.

Correctness, reliability, reproducibility and explainability have higher priority than visual effects or feature count.

Do not fabricate functionality. Do not claim a feature works until it has been implemented and tested.

Do not silently ignore errors.

Do not generate fake analytical insights.

Do not invent statistics.

Do not allow an LLM to calculate statistics that can be calculated deterministically.

When uncertain about a library API, check the current official documentation before implementation rather than relying on obsolete syntax.

---

# PRODUCT DEFINITION

Working product name:

**HaraLens**

Positioning:

**Intelligent Data Health, Analytics & ML Readiness Platform**

Core product promise:

> Understand, validate and improve your data before trusting the decisions or models built from it.

HaraLens should allow users to ingest datasets and automatically profile, validate, diagnose, score, analyze and assess them.

The system should identify problems, quantify their seriousness, explain their analytical consequences, recommend remediation actions, perform statistically defensible advanced analysis, assess machine-learning readiness and generate professional executive and technical reports.

Long term, HaraLens should function as a serious SaaS platform rather than merely a portfolio demonstration.

---

# USERS

HaraLens must serve different audiences through adaptive experiences.

## Executive Mode

Designed for managers and non-technical decision-makers.

Emphasize:

business risks,
overall data health,
critical issues,
business implications,
priority recommendations,
KPIs,
executive summaries,
comparisons over time,
downloadable executive reports.

Avoid unnecessary statistical jargon.

## Analyst Mode

Designed for data analysts, business analysts, students and researchers.

Provide:

data profiling,
quality diagnostics,
visual exploration,
statistical testing,
relationship analysis,
remediation guidance,
target analysis,
guided interpretation.

## Data Scientist / ML Mode

Designed for data scientists and ML practitioners.

Provide:

ML readiness,
feature diagnostics,
leakage detection,
multicollinearity,
target analysis,
baseline models,
cross-validation,
model comparison,
hyperparameter optimization,
explainability,
fairness analysis,
experiment tracking,
model artifacts,
model cards.

The same underlying analytical results must drive all modes. Only depth and presentation should differ.

---

# TECHNOLOGY PRINCIPLES

All required development tools should be free and/or open source wherever practical.

Do not depend on paid APIs.

The system must remain usable without external commercial AI APIs.

Use a modular architecture so individual technologies can later be replaced without rewriting the complete application.

Primary application architecture:

**Streamlit frontend → FastAPI backend → application services → analytics/ML engines → persistence/storage adapters**

Streamlit is the initial frontend.

FastAPI provides the backend API and separation of concerns.

The architecture must allow Streamlit to eventually be replaced by React or another frontend without rewriting the backend, analytics engine or domain layer.

Use `st.Page` and `st.navigation` for Streamlit navigation unless the current Streamlit documentation recommends a superior replacement.

Use Supabase initially for:

PostgreSQL,
authentication,
storage where appropriate,
user management.

However, create abstraction layers so the application is not permanently coupled to Supabase.

Application-specific database access should use repository/service abstractions.

The underlying persistent relational database is PostgreSQL.

Authentication implementation must be replaceable.

Storage implementation must be replaceable.

Use Ollama for optional local open-source LLM functionality.

The application must remain fully functional when Ollama is unavailable.

AI capabilities are enhancements, not dependencies for core analytical correctness.

---

# CRITICAL AI RULE

Follow this pipeline:

**Data → deterministic computation → validated structured findings → rule engine → optional LLM interpretation**

Never use:

**Data → LLM → guessed analytics**

The LLM may explain:

statistical findings,
quality problems,
business implications,
recommendations,
executive summaries,
technical summaries,
natural-language questions about previously computed results.

The LLM must NOT invent:

means,
medians,
correlations,
p-values,
feature importance,
model metrics,
missing percentages,
health scores,
outlier counts,
confidence intervals,
sample sizes,
or any other analytical quantity.

LLM prompts must be grounded using structured results generated by HaraLens.

Raw sensitive datasets must not be sent to the LLM by default.

Prefer sending metadata and aggregated analytical results.

---

# DATA SOURCES

Design connectors through a common ingestion interface.

Supported roadmap:

CSV
Excel
Parquet
JSON
REST APIs
PostgreSQL
MySQL
SQL Server
Google Sheets
supported cloud-storage integrations where technically practical without paid dependencies.

Implement these incrementally.

Phase-one ingestion must prioritize:

CSV
Excel
Parquet

Database and API connectors should follow after the core engine is stable.

Database connectors should support read-only operation.

Never require database administrator credentials when read-only credentials are sufficient.

Guard against arbitrary destructive SQL.

API connectors must include timeout handling, response-size constraints and SSRF-aware validation.

---

# SCALE AND PERFORMANCE

HaraLens should work on ordinary laptops but be architected to handle much larger datasets.

Do not blindly load arbitrarily large files into pandas.

Create a data-engine abstraction capable of choosing suitable strategies.

Use technologies such as:

Pandas for broad compatibility,
Polars where beneficial,
PyArrow for columnar operations,
DuckDB for efficient analytical querying and larger-than-memory workflows where appropriate.

Implement resource-aware behavior.

Before expensive operations, inspect:

row count,
column count,
file size,
available memory where detectable,
data types,
estimated computational cost.

For large datasets, support:

sampling,
chunked processing,
lazy evaluation,
incremental profiling where feasible,
progress indicators,
cancellation where feasible,
clear warnings when an operation is expensive.

Results derived from samples must clearly state that sampling was used.

Never present sampled statistics as exact full-dataset statistics.

---

# CORE SOFTWARE ARCHITECTURE

Use a monorepo.

A strong initial structure should resemble:

```text
haralens/
│
├── apps/
│   ├── streamlit/
│   └── api/
│
├── src/
│   └── haralens/
│       ├── domain/
│       ├── ingestion/
│       ├── profiling/
│       ├── quality/
│       ├── scoring/
│       ├── analytics/
│       ├── statistics/
│       ├── ml/
│       ├── ai/
│       ├── governance/
│       ├── reporting/
│       ├── collaboration/
│       ├── automation/
│       ├── security/
│       ├── persistence/
│       └── common/
│
├── migrations/
├── tests/
│   ├── unit/
│   ├── integration/
│   ├── api/
│   ├── ui/
│   ├── security/
│   └── performance/
│
├── sample_data/
├── docs/
├── scripts/
├── docker/
├── .github/
│   └── workflows/
├── pyproject.toml
├── README.md
├── .env.example
├── docker-compose.yml
├── LICENSE
└── SECURITY.md
```

You may improve this architecture when technically justified.

Do not place business logic directly inside Streamlit pages.

Do not place statistical calculations inside UI callbacks.

Do not place database logic throughout unrelated application modules.

Use clear boundaries between:

domain logic,
application services,
infrastructure,
analytics,
presentation.

---

# DOMAIN MODELS

Create typed domain models for major objects.

Examples include:

User
Organization
Workspace
Project
Dataset
DatasetVersion
DataSource
ColumnProfile
QualityCheck
QualityFinding
HealthScore
AnalysisRun
StatisticalTestResult
Recommendation
MLExperiment
ModelArtifact
ModelVersion
Report
ValidationRule
ScheduledJob
Notification
Comment
Approval
AuditEvent

Use Pydantic or appropriate typed domain models.

Avoid passing unstructured dictionaries throughout the entire codebase.

---

# DATA PROFILING ENGINE

Create a reusable profiling engine independent of Streamlit.

Given a tabular dataset, it should produce structured profile objects.

Dataset-level information should include:

row count,
column count,
memory footprint,
duplicate count,
missing-cell count,
missing percentage,
inferred dataset characteristics,
type distribution,
constant-column count,
potential identifier count,
potential target candidates where reasonable.

Column profiling should detect and calculate appropriate information for:

numerical,
categorical,
boolean,
datetime,
identifier,
free text,
potential PII.

Numerical profiles should include appropriate descriptive statistics such as:

count,
missing values,
unique values,
minimum,
maximum,
mean,
median,
standard deviation,
variance,
quartiles,
IQR,
skewness,
kurtosis,
zero frequency,
infinite values,
potential outliers.

Categorical profiles should include:

unique count,
cardinality ratio,
mode,
frequency,
rare categories,
entropy where appropriate,
missingness,
potential inconsistent categories.

Datetime profiles should include:

minimum date,
maximum date,
invalid dates,
future dates,
missingness,
range,
frequency patterns where defensible.

Profiles must be serializable so they can be saved and reproduced.

---

# TYPE INFERENCE ENGINE

Do not blindly trust pandas dtypes.

Create an inference layer to distinguish:

true numeric features,
categorical features,
boolean values,
dates represented as strings,
identifiers represented numerically,
free-text columns,
potential PII.

Use transparent heuristics.

Record:

original type,
inferred semantic type,
confidence where useful,
reason for inference.

Users must be able to override inferred semantic types.

Overrides should be stored with project configuration.

---

# DATA QUALITY ENGINE

Create a plugin-style quality-check framework.

Every check must return a standardized result containing at minimum:

check identifier,
check name,
quality dimension,
status,
severity,
column or dataset scope,
affected count,
affected percentage where applicable,
evidence,
human-readable explanation,
analytical/business impact,
recommended action,
calculation metadata.

Initial quality dimensions:

Completeness
Uniqueness
Validity
Consistency
Integrity
Analytical Readiness

Initial checks should cover professionally meaningful issues including:

missing values,
high missingness,
duplicate rows,
duplicate identifiers,
constant features,
near-zero variance,
invalid numerical values,
infinite values,
mixed types,
invalid dates,
future dates where unexpected,
range violations,
category inconsistencies,
leading/trailing whitespace,
case inconsistencies,
rare categories,
high cardinality,
extreme skewness,
univariate outliers,
suspicious zeros,
high feature correlation,
multicollinearity,
target imbalance,
potential identifiers,
potential PII,
potential data leakage,
schema violations.

Make checks configurable.

Users should eventually be able to disable checks or change thresholds.

---

# SCHEMA AND BUSINESS-RULE VALIDATION

Use Pandera or an equivalent open-source validation layer where appropriate.

Allow users to define reusable validation rules including:

required columns,
data types,
nullable/non-nullable,
allowed ranges,
allowed category sets,
regex rules,
uniqueness,
business constraints.

Validation rules should belong to projects and be reusable across dataset versions.

Support validation reports.

Never automatically delete invalid records simply because validation fails.

Diagnosis must precede remediation.

---

# DATA HEALTH SCORING

Create a transparent scoring methodology.

Do not use arbitrary unexplained formulas.

Scores must be explainable to users.

Support dimension scores and an overall score.

Initial dimensions:

Completeness
Uniqueness
Validity
Consistency
Integrity
Analytical Readiness

Use a bounded penalty framework.

Conceptually:

```text
dimension_score = 100 - normalized_weighted_penalties
```

Overall score should be derived from weighted dimension scores.

Penalty magnitude should consider:

severity,
affected proportion,
check importance,
dataset context where defensible.

All scores must remain between 0 and 100.

Store:

formula version,
weights,
threshold configuration,
calculation details.

This allows historical comparisons even if scoring methodology later changes.

Users must be able to inspect why a score was assigned.

Do not allow a single issue to produce mathematically nonsensical negative scores.

Write comprehensive unit tests for scoring.

---

# RECOMMENDATION ENGINE

Build deterministic recommendations first.

Each important finding should answer:

What is wrong?

Why does it matter?

What should the user investigate or do next?

Recommendations should be prioritized as:

Immediate
High priority
Medium priority
Optional

Never automatically recommend deletion merely because data contains missing values or outliers.

Recommendations must respect analytical context.

Example:

Instead of:

"Delete outliers."

Prefer:

"Inspect whether these observations represent data-entry errors, legitimate rare cases or a heavy-tailed distribution before applying treatment."

The optional LLM may rewrite structured recommendations into executive language, but may not change the underlying evidence.

---

# ADVANCED ANALYTICS ENGINE

Build advanced analysis as a separate reusable service.

Numerical analysis should support relevant descriptive and distributional statistics.

Numerical-to-numerical relationships should support appropriate methods such as:

Pearson correlation,
Spearman correlation,
robust alternatives where justified.

Categorical-to-categorical relationships should support:

contingency tables,
chi-square tests,
Cramér's V.

Numerical-to-categorical relationships should support appropriate tests such as:

t-tests,
ANOVA,
Mann-Whitney,
Kruskal-Wallis,

depending on design and assumptions.

Support effect sizes where applicable.

Do not report only p-values.

Where appropriate report:

effect size,
confidence interval,
sample size,
test statistic,
p-value,
assumptions,
limitations.

Use assumption checking where analytically justified.

Do not pretend automated assumption tests are infallible.

Flag when results require expert interpretation.

Support multiple-testing corrections when performing many simultaneous hypothesis tests.

---

# MISSINGNESS ANALYSIS

Go beyond missing percentages.

Support:

missingness matrix/pattern summaries,
co-missingness,
missingness relationships with other variables,
potential MCAR/MAR/MNAR discussion only where scientifically defensible.

Never claim MAR or MNAR has been proven purely from observed data.

---

# TARGET-AWARE ANALYSIS

Allow a user to select a target variable.

Infer whether the likely task is:

binary classification,
multiclass classification,
regression,

while allowing manual override.

Target-aware diagnostics should include:

target missingness,
class balance,
target distribution,
feature-target associations,
potential leakage,
identifier leakage,
temporal leakage where detectable,
highly redundant predictors,
required preprocessing,
potential transformations.

---

# ML READINESS ENGINE

Produce an interpretable ML Readiness Score separate from general Data Health.

Assess areas such as:

target quality,
missingness,
sample size,
feature types,
cardinality,
imbalance,
leakage,
multicollinearity,
duplicate observations,
encoding needs,
scaling needs,
distribution concerns,
data-splitting concerns.

Every deduction must have a reason.

Do not imply that a high readiness score guarantees a high-performing ML model.

---

# MACHINE LEARNING WORKBENCH

After readiness analysis is stable, implement an AutoML-style workflow built transparently around standard open-source libraries.

Do not create a black box.

Support baseline models first.

Classification may include appropriate algorithms such as:

Logistic Regression
Decision Tree
Random Forest
HistGradientBoosting
SVM where dataset size permits

Regression may include:

Linear Regression
Ridge
Lasso
Elastic Net
Decision Tree Regressor
Random Forest Regressor
HistGradientBoosting Regressor

Additional open-source estimators may be added when justified.

Use scikit-learn pipelines.

Prevent train-test leakage.

Fit preprocessing only on training folds.

Use appropriate cross-validation.

For time-sensitive data, do not use random splits when they would create temporal leakage.

Support model comparison using relevant metrics.

Classification should consider:

accuracy,
precision,
recall,
F1,
ROC-AUC where appropriate,
PR-AUC where appropriate,
log loss where appropriate,
confusion matrix.

Regression should consider:

MAE,
RMSE,
R²,
MAPE only where mathematically appropriate.

Do not select models using a single metric without explanation.

---

# HYPERPARAMETER OPTIMIZATION

Use Optuna or an equivalent professional open-source optimization framework.

Optimization must have:

bounded search spaces,
reproducible seeds,
maximum trial limits,
timeouts,
pruning where appropriate,
stored optimization history.

Do not launch huge tuning jobs by default.

Use resource-aware presets.

Store every study configuration.

---

# EXPERIMENT TRACKING AND MODEL REGISTRY

Use MLflow for experiment tracking and model lifecycle management.

Record:

dataset version,
feature configuration,
preprocessing pipeline,
random seed,
model algorithm,
hyperparameters,
metrics,
artifacts,
training timestamp,
code version where feasible.

Support model registration and version history.

Do not overwrite previous experiments.

---

# EXPLAINABLE AI

Support explainability using appropriate techniques such as:

native feature importance,
permutation importance,
SHAP where appropriate.

Clearly distinguish global from local explanations.

Warn users that feature importance is not necessarily causal.

Do not describe correlation or feature importance as causation.

---

# FAIRNESS AND RESPONSIBLE ML

Add optional fairness analysis using open-source tooling such as Fairlearn when a user intentionally identifies a sensitive or comparison attribute.

Do not automatically guess legally protected characteristics from names or proxies.

Support metrics appropriate to task context.

Include limitations.

Create governance-ready fairness summaries.

---

# MODEL AND DATA CARDS

Generate structured dataset cards and model cards.

Dataset cards should document:

source,
version,
schema,
quality,
known limitations,
intended use,
sensitive fields,
transformations.

Model cards should document:

training data version,
intended use,
unsupported uses,
algorithm,
evaluation metrics,
fairness analysis when available,
limitations,
feature set,
model version.

---

# FUTURE ANALYTICS MODULES

Design interfaces now, but implement after the tabular platform is stable.

Future engines:

Time-Series Analytics
Text/NLP Analytics
Geospatial Analytics
Network/Graph Analytics

These should be independent modules with common result interfaces.

Do not delay the core product attempting to implement all of them simultaneously.

---

# LOCAL AI ASSISTANT

Use Ollama as the primary local LLM integration.

Create an AI provider interface so Ollama can later be replaced or complemented.

Functions may include:

Explain this health report
Explain this statistical result
Summarize the most important risks
Generate an executive summary
Explain recommended remediation
Answer questions about computed analysis
Explain model performance
Explain model limitations

The assistant must receive structured evidence.

Implement prompt templates and version them.

Responses should cite internal finding identifiers where feasible.

If the AI service is offline, HaraLens must continue functioning and show a clear message that AI interpretation is unavailable.

---

# SaaS USER MANAGEMENT

Implement authentication through a Supabase adapter.

Support architecture for:

signup,
login,
logout,
password reset,
verified identities where configured,
session handling.

Never trust frontend-provided user identifiers.

Authorize on the server.

Use PostgreSQL Row Level Security where appropriate.

Design organization/workspace structures.

---

# MULTI-TENANCY

The data model must support:

users,
organizations,
workspaces,
projects,
memberships.

Roles should support at minimum:

Owner
Admin
Analyst
Viewer

All project and dataset access must be scoped to appropriate users/workspaces.

Write tests specifically attempting cross-tenant access.

A user from Organization A must not be able to retrieve Organization B's data by guessing identifiers.

---

# COLLABORATION

Long-term collaboration capabilities:

project invitations,
comments,
activity history,
shared reports,
approval workflows,
audit trails.

Build foundational data models first.

Do not prioritize live collaboration before core analytics are reliable.

---

# PRIVACY AND SECURITY

Treat privacy as a core system property.

Support per-project retention mode:

temporary processing,
persistent storage.

Temporary data should have lifecycle cleanup.

Persistent data must have explicit ownership.

Security requirements include:

strict tenant isolation,
authorization,
least privilege,
secure secret management,
safe file handling,
secure temporary files,
filename sanitization,
upload-size limits,
content validation,
SQL injection prevention,
XSS-aware rendering,
API authentication,
rate-limiting architecture,
CSRF-aware design where relevant,
SSRF defenses for external URL/API connectors,
audit logging,
safe error messages.

Never commit secrets.

Provide `.env.example`, never a real `.env`.

Never log:

passwords,
access tokens,
refresh tokens,
database passwords,
raw sensitive datasets.

Potential PII detection should be clearly described as heuristic, not guaranteed.

---

# AUDITABILITY AND GOVERNANCE

Record important events such as:

login,
dataset upload,
dataset deletion,
analysis execution,
rule changes,
report generation,
model training,
model registration,
project-sharing changes,
approval events.

Audit logs should include relevant actor, action, resource and timestamp information without exposing sensitive content unnecessarily.

---

# DATA LINEAGE AND VERSIONING

Datasets should support versions.

Analyses must refer to specific dataset versions.

Store metadata necessary to reproduce an analysis.

Where appropriate store:

dataset hash,
source configuration,
schema,
transformations,
analysis configuration,
code/application version.

Never silently replace dataset versions used by historical reports.

---

# REPORTING

Build two primary report types.

Executive Report:

business-oriented,
health score,
risk summary,
major findings,
priority recommendations,
trends,
concise visualizations.

Technical Report:

dataset metadata,
quality-check catalogue,
detailed findings,
scoring methodology,
statistical analyses,
ML readiness,
model evaluation where applicable,
methodology,
limitations,
reproducibility information.

Use HTML as a first-class report format.

Provide PDF generation through a clean reporting adapter.

Provide CSV export for issue registers.

Allow users to customize report sections later.

Long-term support:

scheduled reports,
report history,
historical comparisons,
shareable controlled links.

---

# HISTORICAL MONITORING

When multiple dataset versions exist, compare health over time.

Support metrics such as:

health-score change,
schema drift,
missingness drift,
distribution drift,
category drift,
model performance drift where applicable.

Use statistically appropriate drift metrics.

Do not label ordinary sampling variability as severe drift without thresholds and context.

---

# AUTOMATION

Design a job abstraction.

Local development should support synchronous execution.

Production architecture may use an open-source background queue such as Redis + RQ or another justified solution.

Future scheduled jobs should support:

data refresh,
quality scans,
health checks,
drift detection,
report generation,
alerts,
model retraining triggers.

A trigger should not automatically retrain and deploy models without safeguards and approval policies.

---

# NOTIFICATIONS

Create a provider abstraction.

Initial notifications can remain in-app.

Architect for future email/other channels.

Possible triggers:

critical health deterioration,
schema break,
failed data refresh,
drift threshold exceeded,
scheduled report ready,
model-performance degradation.

---

# REPORT AND ALERT SEVERITY

Use a consistent severity taxonomy:

Critical
High
Medium
Low
Passed / Informational

Severity thresholds must be configurable.

Do not make everything Critical.

---

# PROFESSIONAL UI/UX

The initial Streamlit interface should feel like a product rather than a collection of scripts.

Use strong information hierarchy.

Provide:

onboarding,
empty states,
help text,
progress states,
error states,
success states,
tooltips,
consistent navigation,
responsive layouts where Streamlit allows,
clear calls to action.

Avoid excessive emojis.

Avoid rainbow dashboards.

Avoid dozens of unrelated charts.

Every visualization must answer a question.

Core navigation should ultimately include areas such as:

Home
Workspace
Projects
Data Sources
Dataset Overview
Data Health
Quality Diagnostics
Advanced Analysis
Target Analysis
ML Readiness
ML Workbench
AI Assistant
Reports
Automation
Governance
Settings

Hide unavailable modules cleanly rather than presenting broken controls.

---

# VISUALIZATION STANDARDS

Use Plotly or an appropriately justified visualization library.

Charts must include:

meaningful titles,
axis labels,
units,
appropriate number formats,
sensible sorting,
clear legends,
accessible presentation.

Avoid misleading axes.

Avoid unnecessary 3D charts.

Avoid pie charts when a more interpretable chart is available.

Large datasets should use aggregation/sampling appropriate to the visualization.

---

# HEALTH DASHBOARD

The health dashboard should clearly surface:

Overall Health Score
Dimension Scores
Critical Issues
Warnings
Passed Checks
Top Risks
Priority Actions
Health Trend when historical data exists

Allow users to drill from a dimension into the findings that affected the score.

---

# ISSUE REGISTER

Generate a structured issue register.

Each issue should include:

ID
Dataset version
Column/scope
Dimension
Severity
Status
Affected count
Affected percentage
Problem
Evidence
Impact
Recommendation
Created timestamp
Resolution status

Allow export to CSV.

---

# REMEDIATION

Diagnosis should precede transformation.

Do not initially implement a dangerous universal "Clean My Dataset" button.

When transformations are introduced, provide:

recommended change,
reason,
preview,
affected rows,
before/after comparison,
ability to approve/reject,
transformation history.

Never modify the original dataset in place.

Create a new dataset version.

---

# DATABASE DESIGN

Use PostgreSQL migrations.

Create normalized, maintainable tables.

Use UUIDs where appropriate.

Add indexes intentionally.

Do not over-index.

Use created/updated timestamps.

Design deletion/retention behavior explicitly.

Use foreign-key constraints.

Create row-level authorization policies when appropriate.

Keep database migrations version-controlled.

---

# API DESIGN

FastAPI endpoints must be versioned, for example:

`/api/v1/...`

Use Pydantic request and response schemas.

Generate OpenAPI documentation.

Return consistent errors.

Do not expose Python stack traces to production users.

Add:

health endpoint,
readiness endpoint where useful.

Separate routers by domain.

---

# ERROR HANDLING

Create domain-specific exceptions.

Distinguish:

validation errors,
authentication errors,
authorization errors,
not found,
conflict,
unsupported data,
resource limitations,
internal failures.

Show users actionable error messages.

Log enough technical detail for debugging without leaking sensitive information.

---

# OBSERVABILITY

Implement structured logging.

Include request/run correlation identifiers where useful.

Design for future metrics and tracing.

Record performance for expensive operations.

Do not make external telemetry mandatory.

Privacy must take priority.

---

# DEVELOPMENT TOOLING

Use a modern Python project configuration through `pyproject.toml`.

Prefer a modern environment/package workflow such as `uv` if compatible with the current ecosystem.

Use:

Ruff
pytest
pytest-cov
mypy or justified type checking
pre-commit
appropriate security linting

Use strict-enough configuration without making development impossible.

Pin/reproduce dependency versions through a lockfile.

---

# TESTING STRATEGY

Testing is mandatory.

Unit tests must cover:

quality checks,
scoring,
profiling,
statistical functions,
recommendations,
type inference,
ML readiness.

Integration tests must cover:

database repositories,
authentication integration,
storage adapters,
analysis workflows.

API tests must cover FastAPI endpoints using current recommended FastAPI testing practices.

UI tests should use Streamlit AppTest where appropriate.

Security tests should include authorization and tenant-isolation scenarios.

Performance tests should cover representative large datasets.

Create synthetic datasets designed to expose failures:

clean dataset
missing-data dataset
duplicates
invalid dates
mixed types
extreme outliers
imbalanced classification
high cardinality
constant columns
correlated predictors
leakage examples

Analytical tests should compare results against known expected values.

Randomized processes must use reproducible seeds in tests.

---

# STATISTICAL VALIDATION

Analytical correctness is non-negotiable.

For every statistical method:

document assumptions,
document output,
test against known examples,
handle insufficient sample sizes,
handle zero-variance features,
handle missing data intentionally,
handle numerical instability.

Never return `nan` without explanation when it indicates an analytical limitation.

---

# CI/CD

Create GitHub Actions workflows.

At minimum CI should run:

format/lint checks,
type checks where configured,
unit tests,
integration tests where practical,
coverage,
security checks.

Do not deploy when critical tests fail.

Production deployment should eventually use container images.

---

# CONTAINERIZATION

Provide Dockerfiles for relevant services.

Provide `docker-compose.yml` for local development including services needed for the complete local stack when practical.

Production architecture should be container-ready.

Local development must remain convenient.

---

# DEPLOYMENT STRATEGY

Provide separate profiles.

## Local Development

Everything should be runnable locally using free/open-source tooling.

Ollama should be optional.

## Free Public Demo

Use the most practical free deployment options available at implementation time.

Streamlit Community Cloud may be used for the frontend demonstration.

Supabase Free may be used for initial database/auth/storage requirements.

If free infrastructure cannot host the full separated backend architecture reliably, provide a demo compatibility mode rather than compromising the production architecture.

Clearly document limitations.

## Production Architecture

Containerized frontend/backend/workers.

Production-grade PostgreSQL/Supabase configuration.

Reverse proxy/load-balancing architecture when required.

Secure secrets.

Persistent storage.

Background workers.

Monitoring.

Do not pretend a high-availability SaaS platform can operate indefinitely at meaningful scale with zero infrastructure cost.

---

# COMMERCIAL ARCHITECTURE

Do not activate payments initially.

However, design entitlements so future plans are possible:

Free
Professional
Team
Enterprise

Potential entitlements can control:

number of projects,
dataset size,
analysis runs,
scheduled scans,
retention,
team members,
ML features,
automation,
API access.

Do not scatter plan checks throughout the code.

Create a centralized entitlement/feature-gating service.

---

# API ACCESS

Design future customer API access.

Do not implement insecure permanent API keys casually.

Create architecture for:

scoped credentials,
revocation,
usage limits,
audit logs.

Implement only after core application authentication is secure.

---

# DOCUMENTATION

Maintain documentation while building.

Required documentation should eventually include:

README
architecture overview
local setup
environment configuration
database setup
Supabase setup
Ollama setup
testing instructions
deployment instructions
scoring methodology
quality-check catalogue
statistical methodology
ML methodology
security model
privacy design
limitations
contribution guide
API documentation
roadmap.

README must not exaggerate unimplemented features.

Use a feature-status table or equivalent to distinguish:

Implemented
Experimental
Planned

---

# README QUALITY

The GitHub README should eventually demonstrate:

problem,
solution,
product screenshots,
architecture,
major capabilities,
technical stack,
methodology,
health-score calculation,
security/privacy approach,
quick start,
testing,
sample workflow,
roadmap,
known limitations.

The repository should be understandable to a recruiter or engineer without opening every source file.

---

# CODE QUALITY RULES

Write production-quality code.

Use:

clear naming,
small cohesive functions,
typed interfaces,
docstrings where genuinely useful,
separation of concerns,
dependency injection where appropriate,
repository patterns where justified,
configuration objects,
consistent logging.

Avoid:

massive god classes,
massive files,
copy-pasted logic,
global mutable state,
hidden side effects,
magic numbers,
hardcoded secrets,
deep unnecessary inheritance,
overengineering.

Prefer composition.

---

# PERFORMANCE RULES

Profile before optimizing.

Cache deterministic expensive results based on dataset/version/configuration hashes.

Do not recompute expensive profiles after every Streamlit rerun.

Use Streamlit caching correctly for frontend-level computations/resources.

Cache invalidation must be explicit when dataset versions or configurations change.

---

# REPRODUCIBILITY

Every analysis run should capture enough configuration to explain:

what data was analyzed,
which version,
which options,
which thresholds,
which random seed,
which scoring version,
which code/application version where possible,
when it ran.

Historical reports must not mysteriously change because a later configuration changed.

---

# PROJECT PHASES

Do NOT attempt to implement everything simultaneously.

Implement in this order.

## Phase 0 — Product and Architecture Foundation

Create:

repository,
project configuration,
architecture documentation,
domain models,
configuration layer,
logging,
basic CI,
test skeleton,
Docker foundations,
development instructions.

Define interfaces before infrastructure becomes tightly coupled.

Acceptance condition:

Project installs cleanly, tests run and architecture documentation exists.

## Phase 1 — Core Tabular Engine

Implement:

CSV/Excel/Parquet ingestion,
semantic type inference,
dataset profiling,
column profiling,
quality-check framework,
initial checks,
health-score engine,
recommendations.

No fancy UI should compensate for an incomplete engine.

Acceptance condition:

A DataFrame can be passed through the engine without Streamlit and return a deterministic structured health assessment.

## Phase 2 — Professional Streamlit Experience

Implement:

navigation,
upload flow,
projects,
dataset overview,
health dashboard,
quality diagnostics,
issue register,
recommendations,
adaptive Executive/Analyst/Data Scientist modes.

Acceptance condition:

A new user can upload a dataset and understand its condition without reading source code.

## Phase 3 — Authentication and SaaS Persistence

Implement:

Supabase auth adapter,
users,
organizations,
workspaces,
projects,
dataset metadata,
analysis history,
RLS/authorization,
storage strategy,
tenant-isolation tests.

Acceptance condition:

Two organizations cannot access each other's resources.

## Phase 4 — FastAPI Service Layer

Expose the core capabilities through versioned API endpoints.

Streamlit must use service abstractions rather than duplicating analytics logic.

Acceptance condition:

Major analysis workflows can be executed programmatically through tested APIs.

## Phase 5 — Advanced Analytics

Implement:

association analysis,
statistical testing,
effect sizes,
missingness analysis,
assumption diagnostics,
target-aware analysis,
professional interpretations.

Acceptance condition:

Automated statistical results are tested against known expected outputs.

## Phase 6 — ML Readiness

Implement:

problem-type inference,
target diagnostics,
leakage analysis,
preprocessing advisor,
ML readiness score.

Acceptance condition:

Every readiness deduction is traceable to evidence.

## Phase 7 — ML Workbench

Implement:

preprocessing pipelines,
baseline modeling,
cross-validation,
model comparison,
Optuna tuning,
MLflow tracking,
model registry,
explainability,
model cards,
fairness layer.

Acceptance condition:

Experiments are reproducible and no preprocessing leakage occurs.

## Phase 8 — Local AI

Implement:

Ollama provider,
structured context builder,
AI explanations,
executive summaries,
analysis Q&A,
prompt versioning,
fallback behavior.

Acceptance condition:

Turning Ollama off does not break HaraLens.

## Phase 9 — Reporting and Governance

Implement:

executive report,
technical report,
issue export,
dataset cards,
model cards,
audit history,
lineage,
version comparisons.

Acceptance condition:

A report can be traced to the exact dataset and analysis configuration that produced it.

## Phase 10 — Automation

Implement:

job abstraction,
scheduled scans,
refresh architecture,
alerts,
notifications,
report scheduling,
drift analysis foundations.

Acceptance condition:

Scheduled work cannot bypass authorization and failures are observable.

## Phase 11 — Additional Data Connectors

Add:

JSON,
REST APIs,
PostgreSQL,
MySQL,
SQL Server,
Google Sheets,
other justified connectors.

Every connector requires tests and error handling.

## Phase 12 — Advanced Analytical Modules

Incrementally add:

time series,
NLP,
geospatial,
network analysis.

Do not build these until the tabular product is stable.

## Phase 13 — Production Hardening

Perform:

security review,
performance testing,
access-control review,
dependency review,
failure testing,
large-file testing,
backup/restore documentation,
deployment hardening,
UX review,
accessibility review,
documentation review.

---

# AGENT WORKING METHOD

You are not allowed to generate hundreds of files blindly.

At the beginning of each phase:

inspect the repository,
read existing architecture documentation,
identify dependencies,
state the objective,
state acceptance criteria,
state files expected to change.

Then implement the smallest coherent vertical slice.

After implementation:

run formatting,
run linting,
run tests,
run type checks when configured,
manually inspect critical workflows,
fix failures,
update documentation.

Do not mark the phase complete while relevant tests are failing.

Do not delete working code simply to make tests pass.

Do not weaken tests to hide bugs.

---

# CODING-AGENT COMMUNICATION

When working inside the repository, communicate concisely.

For each meaningful implementation cycle report:

what changed,
why it changed,
tests executed,
results,
known limitations,
next recommended task.

Do not overwhelm the user with every internal implementation detail.

---

# FAILURE POLICY

When an implementation fails:

diagnose the root cause,
inspect logs,
create the smallest reproducible failure,
fix the underlying issue,
add a regression test.

Do not apply random package upgrades or downgrades without explaining why.

---

# DEPENDENCY POLICY

Prefer mature, actively maintained dependencies.

Before adding a dependency ask:

Is it necessary?
Can the standard library/current stack solve this?
Is it maintained?
What security/maintenance burden does it create?
Does it materially simplify the implementation?

Avoid dependency inflation.

---

# SECURITY REVIEW CHECKPOINTS

Perform explicit security reviews before:

public deployment,
database connector release,
API connector release,
team collaboration release,
customer API release,
automation release.

Review authentication, authorization, tenancy boundaries, secrets, injection risks and data exposure.

---

# QUALITY BAR

A feature is not complete because the UI renders.

A feature is complete when:

its requirements are defined,
its domain behavior is implemented,
edge cases are considered,
errors are handled,
tests pass,
security implications are addressed,
documentation is updated,
UX communicates the result correctly.

---

# ANALYTICS QUALITY BAR

An analytical feature is not complete because it returns a number.

It must have:

correct methodology,
known assumptions,
tested calculations,
interpretable output,
limitations,
edge-case handling.

---

# DEFINITION OF SUCCESS

HaraLens should eventually demonstrate professional ability across:

software architecture,
Python engineering,
API development,
database design,
authentication,
SaaS architecture,
data quality,
statistics,
EDA,
machine learning,
MLOps,
AI integration,
explainability,
governance,
security,
testing,
DevOps,
product design,
business communication.

However, never sacrifice depth for the appearance of breadth.

The strongest HaraLens is not the version containing the largest number of menu items.

It is the version users can trust.

---

# FIRST EXECUTION INSTRUCTION

Do NOT start by implementing the entire roadmap.

Start with **Phase 0**.

First inspect the current repository.

If the repository is empty, initialize the professional repository structure.

Then produce:

`docs/PRODUCT_SPEC.md`

`docs/ARCHITECTURE.md`

`docs/ROADMAP.md`

`docs/SCORING_METHODOLOGY.md`

initial `README.md`

`pyproject.toml`

`.gitignore`

`.env.example`

base package structure

test structure

GitHub Actions CI skeleton

basic FastAPI health endpoint

minimal Streamlit shell using `st.navigation`

configuration and logging foundations.

After creating these foundations, run the project and tests.

Report exactly:

what was created,
which commands were run,
which tests passed,
which tests failed,
any assumptions made,
the exact next Phase 1 task.

Do not proceed into Phase 1 until Phase 0 is internally consistent.

Begin now.
