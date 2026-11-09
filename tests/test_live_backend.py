import os
from unittest.mock import patch

from fastapi.testclient import TestClient

import live_backend


def test_health_is_available():
    response = TestClient(live_backend.app).get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_realtime_requires_server_key():
    with patch.dict(os.environ, {}, clear=True):
        response = TestClient(live_backend.app).post(
            "/api/realtime/session", json={"teacher": "Female", "ayah": ""}
        )
    assert response.status_code == 503
    assert "OPENAI_API_KEY" in response.json()["detail"]


def test_realtime_rejects_invalid_teacher():
    response = TestClient(live_backend.app).post(
        "/api/realtime/session", json={"teacher": "Other", "ayah": ""}
    )
    assert response.status_code == 422
