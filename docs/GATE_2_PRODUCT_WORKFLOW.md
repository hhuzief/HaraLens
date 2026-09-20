# Gate 2 product workflow

HaraLens Gate 2 keeps the Streamlit layer as a presentation consumer of one canonical service:

```text
uploaded bytes + safe filename
        ↓
analyze_uploaded_dataset
        ↓
bounded ingestion → semantic inference → profiling → quality runner
        ↓
health scorer → recommendation engine
        ↓
session-scoped AnalysisResult → Streamlit tabs
```

The service is implemented in `src/haralens/application/analysis.py`. It selects the
hardened adapter by extension, passes configured `Settings.ingestion_limits`, handles Excel
worksheet selection through the typed ingestion exception, and returns a single typed result.
Raw upload bytes are not retained in that result.

The application has Home, Analyze, and Methodology/About views. Analyze stores only the current
`AnalysisResult`, upload identity, safe source name, worksheet choice, and error state in the
current Streamlit session. Reset clears all of these values before another analysis.

Results contain Overview, Quality, Columns, and Recommendations tabs. Every score, finding,
profile fact, chart source, and recommendation is derived from the engine result. No raw dataset
table is rendered by default, no global cache is used, and no application endpoint or persistence
layer was added in Gate 2.
