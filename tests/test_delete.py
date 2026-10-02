from fastapi.testclient import TestClient

from app.main import app


def test_health_still_available():
    with TestClient(app) as client:
        assert client.get("/health").status_code == 200
