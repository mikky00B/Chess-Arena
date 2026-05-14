from fastapi.testclient import TestClient

from app.main import create_app


def test_health_live() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "service": "chess-arena-v2"}


def test_health_ready_reports_foundation_config() -> None:
    client = TestClient(create_app())

    response = client.get("/health/ready")

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["environment"]
    assert body["checks"]["app"] == "ok"
    assert body["checks"]["database"] == "configured"
    assert body["checks"]["redis"] == "configured"


def test_request_id_header_is_returned() -> None:
    client = TestClient(create_app())

    response = client.get("/health/live", headers={"x-request-id": "test-request"})

    assert response.headers["x-request-id"] == "test-request"
