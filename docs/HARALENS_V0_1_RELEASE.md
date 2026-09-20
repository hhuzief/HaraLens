# HaraLens v0.1 release boundary

Gate 1 provides deterministic production quality checks, explainable methodology scores, and
traceable recommendations for an uploaded tabular dataset. It evaluates data against configured
HaraLens rules; it does not guarantee clean data, universal statistical validity, or ML readiness.

Gate 2 provides the session-scoped Streamlit workflow for uploading supported files and viewing
those engine results. It does not add persistence, authentication, reporting, or automatic cleaning.

The engine is independent of Streamlit, FastAPI, persistence, authentication, connectors, AI,
and automatic cleaning. Gate 2 integration should use the public imports:

```python
from haralens.quality import QualityCheckContext, QualityCheckRunner, QualityFrameworkConfig
from haralens.quality import create_default_quality_registry
from haralens.scoring import HealthScorer
from haralens.recommendations import RecommendationEngine

registry = create_default_quality_registry()
quality = QualityCheckRunner().run(context, registry, QualityFrameworkConfig())
health = HealthScorer().score(quality)
recommendations = RecommendationEngine().generate(quality, health)
```
