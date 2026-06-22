from fastapi.testclient import TestClient

import app.main as main_module
from app.main import app


def test_health_endpoint():
    with TestClient(app) as c:
        response = c.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_endpoint_survives_schema_init_failure(monkeypatch):
    def fail_init_schema():
        raise RuntimeError("postgres unavailable")

    monkeypatch.setattr(main_module, "init_schema", fail_init_schema)

    with TestClient(app) as c:
        response = c.get("/health")

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
