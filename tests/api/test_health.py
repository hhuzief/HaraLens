from fastapi.testclient import TestClient

from haralens import __version__
from haralens.api.app import create_app
from haralens.common.config import Settings


def test_health_and_openapi() -> None:
    with TestClient(create_app(Settings(environment="test"))) as client:
        response = client.get("/api/v1/health")
        assert response.status_code == 200
        assert response.json() == {"status": "ok", "service": "HaraLens", "version": __version__}
        assert "/api/v1/health" in client.get("/openapi.json").json()["paths"]
        assert client.get("/missing").status_code == 404


def test_default_app_factory() -> None:
    with TestClient(create_app()) as client:
        assert client.get("/api/v1/health").status_code == 200
